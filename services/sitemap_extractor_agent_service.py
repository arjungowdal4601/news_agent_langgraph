"""LLM-driven, per-site sitemap URL extractor.

The walker in services/sitemap_service.py is generic and does not adapt to the
shape of each site's sitemap. This service asks an LLM to read a small sample
of one site's top sitemap and write a Python function tailored to that site.
The generated function is cached on disk in configs/sitemap_extractors and
re-executed on later runs.

Safety guardrails:
- Generated code may only import from SITEMAP_EXTRACTOR_WHITELIST.
- An AST scan rejects banned names (open, exec, eval, __import__, subprocess,
  os, sys, attribute access on __builtins__, ...) before the source is
  exec'd.
- Generated code never touches the network. All HTTP/gzip work goes through
  the injected `fetch_xml` helper that the caller passes in.
- Execution is wrapped in a hard timeout.
- If anything fails the caller falls back to the existing recursive walker.
"""

from __future__ import annotations

import ast
import concurrent.futures
import hashlib
import os
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from constants import (
    DEFAULT_OPENAI_MODEL,
    SITEMAP_EXTRACTOR_DIR,
    SITEMAP_EXTRACTOR_TIMEOUT_SECONDS,
    SITEMAP_EXTRACTOR_WHITELIST,
)
from prompts.sitemap_extractor_prompts import SITEMAP_EXTRACTOR_PROMPT


CACHE_HEADER_PREFIX = "# extractor-meta:"
SAMPLE_HEAD_LINES = 30
SAMPLE_TAIL_LINES = 10
SAMPLE_BYTE_BUDGET_HEAD = 6000
SAMPLE_BYTE_BUDGET_TAIL = 2000


class ExtractorContractError(RuntimeError):
    """Raised when generated extractor source violates the safety contract."""


class GeneratedExtractor(BaseModel):
    """Structured output returned by the extractor-generator LLM call."""

    python_code: str = Field(
        description=(
            "Raw Python source defining the top-level function "
            "extract_recent_urls(top_xml_path, cutoff_date, fetch_xml) -> list[dict]."
        )
    )
    notes: str = Field(
        default="",
        description="Short freeform notes about the chosen extraction strategy.",
    )


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------
def inspection_sample(xml_path: str) -> str:
    """Return a small head+tail sample of the top sitemap XML.

    Handles the minified single-line case (e.g. autonews.xml) by truncating
    by byte budget instead of line count.
    """
    text = Path(xml_path).read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()

    if len(lines) <= SAMPLE_HEAD_LINES + SAMPLE_TAIL_LINES + 5:
        head_text = text[:SAMPLE_BYTE_BUDGET_HEAD]
        tail_text = text[-SAMPLE_BYTE_BUDGET_TAIL:] if len(text) > SAMPLE_BYTE_BUDGET_HEAD else ""
        if tail_text and tail_text not in head_text:
            return f"{head_text}\n\n... [truncated] ...\n\n{tail_text}"
        return head_text

    head = "\n".join(lines[:SAMPLE_HEAD_LINES])
    tail = "\n".join(lines[-SAMPLE_TAIL_LINES:])
    return f"{head}\n\n... [truncated {len(lines) - SAMPLE_HEAD_LINES - SAMPLE_TAIL_LINES} middle lines] ...\n\n{tail}"


def sample_hash(sample: str) -> str:
    """Stable 12-char hash used to detect XML structure drift."""
    digest = hashlib.sha256(sample.encode("utf-8", errors="replace")).hexdigest()
    return digest[:12]


# ---------------------------------------------------------------------------
# AST safety scan
# ---------------------------------------------------------------------------
_BANNED_NAMES = {
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",
    "input",
    "breakpoint",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "memoryview",
    "__builtins__",
}

_BANNED_ATTRIBUTES = {
    "__class__",
    "__bases__",
    "__mro__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__import__",
    "__loader__",
    "__spec__",
}


def _scan_ast_for_safety(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ExtractorContractError(f"Generated extractor failed to parse: {exc}") from exc

    whitelist = set(SITEMAP_EXTRACTOR_WHITELIST)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in whitelist:
                    raise ExtractorContractError(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module not in whitelist:
                raise ExtractorContractError(f"Disallowed import-from module: {module}")
        elif isinstance(node, ast.Name):
            if node.id in _BANNED_NAMES:
                raise ExtractorContractError(f"Disallowed name reference: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in _BANNED_ATTRIBUTES:
                raise ExtractorContractError(f"Disallowed attribute access: {node.attr}")


# ---------------------------------------------------------------------------
# Sandboxed exec
# ---------------------------------------------------------------------------
def _build_safe_namespace() -> dict:
    """Construct the only globals visible to generated code."""
    import gzip
    import re
    import datetime as dt
    import urllib.parse

    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "bytes": bytes,
        "dict": dict,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "frozenset": frozenset,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "print": print,
        "range": range,
        "repr": repr,
        "reversed": reversed,
        "set": set,
        "slice": slice,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "Exception": Exception,
        "RuntimeError": RuntimeError,
    }

    return {
        "__builtins__": safe_builtins,
        "ET": ET,
        "gzip": gzip,
        "re": re,
        "datetime": dt,
        "urllib": urllib,
    }


def safe_exec(source: str) -> Callable:
    """AST-scan, exec, and return the `extract_recent_urls` callable."""
    _scan_ast_for_safety(source)

    namespace = _build_safe_namespace()
    try:
        exec(compile(source, "<generated-extractor>", "exec"), namespace)
    except Exception as exc:  # pragma: no cover - defensive
        raise ExtractorContractError(f"Exec of generated extractor failed: {exc}") from exc

    fn = namespace.get("extract_recent_urls")
    if not callable(fn):
        raise ExtractorContractError(
            "Generated source did not define a callable named extract_recent_urls."
        )
    return fn


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------
def _get_extractor_model() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Add it to a .env file in the project root "
            "or set it in your environment before running the pipeline."
        )
    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return ChatOpenAI(model=model_name, temperature=0, api_key=api_key)


def _strip_code_fences(code: str) -> str:
    """Defensive cleanup in case the model wraps code in ```python fences."""
    cleaned = code.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
    return cleaned.strip()


def generate_extractor_code(site_name: str, sample: str, cutoff_date: date) -> tuple[str, str, str]:
    """Call the LLM to generate the extractor source.

    Returns (python_code, notes, model_name).
    """
    model = _get_extractor_model()
    structured_model = model.with_structured_output(GeneratedExtractor)
    chain = SITEMAP_EXTRACTOR_PROMPT | structured_model

    result: GeneratedExtractor = chain.invoke(
        {
            "site_name": site_name,
            "cutoff_date": cutoff_date.isoformat(),
            "xml_sample": sample,
        }
    )

    code = _strip_code_fences(result.python_code)
    return code, result.notes.strip(), model.model_name


# ---------------------------------------------------------------------------
# Cache file persistence
# ---------------------------------------------------------------------------
def _cache_path(site_name: str) -> Path:
    return SITEMAP_EXTRACTOR_DIR / f"{site_name}.py"


def _format_meta_header(
    site_name: str,
    cutoff_date: date,
    sample_digest: str,
    model_name: str,
    notes: str,
) -> str:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    notes_one_line = " ".join(notes.split()) if notes else ""
    return (
        f"{CACHE_HEADER_PREFIX} site={site_name} cutoff={cutoff_date.isoformat()} "
        f"sample_hash={sample_digest} model={model_name} generated_at={timestamp}\n"
        f"# notes: {notes_one_line}\n\n"
    )


def _read_meta_header(cache_file: Path) -> dict:
    if not cache_file.exists():
        return {}
    first_line = cache_file.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
    if not first_line or not first_line[0].startswith(CACHE_HEADER_PREFIX):
        return {}
    body = first_line[0][len(CACHE_HEADER_PREFIX) :].strip()
    meta = {}
    for token in body.split():
        if "=" in token:
            key, value = token.split("=", 1)
            meta[key] = value
    return meta


def _write_cache_file(
    site_name: str,
    code: str,
    cutoff_date: date,
    sample_digest: str,
    model_name: str,
    notes: str,
) -> Path:
    SITEMAP_EXTRACTOR_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(site_name)
    header = _format_meta_header(site_name, cutoff_date, sample_digest, model_name, notes)
    cache_file.write_text(header + code.rstrip() + "\n", encoding="utf-8")
    return cache_file


def _read_cached_source(cache_file: Path) -> str:
    """Return cached source minus the meta header lines."""
    text = cache_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    body_start = 0
    for index, line in enumerate(lines):
        if line.startswith("#"):
            body_start = index + 1
            continue
        break
    return "\n".join(lines[body_start:]).strip() + "\n"


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def load_or_generate_extractor(
    site_name: str,
    xml_path: str,
    cutoff_date: date,
    force: bool = False,
) -> tuple[Callable, str, str, Path]:
    """Return (extractor_callable, source_tag, sample_hash, cache_path).

    source_tag is one of: "cached", "generated", "regenerated".
    """
    sample = inspection_sample(xml_path)
    digest = sample_hash(sample)
    cache_file = _cache_path(site_name)

    if not force and cache_file.exists():
        meta = _read_meta_header(cache_file)
        if meta.get("sample_hash") == digest:
            cached_source = _read_cached_source(cache_file)
            try:
                fn = safe_exec(cached_source)
                return fn, "cached", digest, cache_file
            except ExtractorContractError:
                # Cache is corrupt/unsafe; fall through and regenerate.
                pass

    source_tag = "regenerated" if cache_file.exists() else "generated"
    code, notes, model_name = generate_extractor_code(site_name, sample, cutoff_date)
    fn = safe_exec(code)  # validate before persisting
    _write_cache_file(site_name, code, cutoff_date, digest, model_name, notes)
    return fn, source_tag, digest, cache_file


def run_extractor_with_timeout(
    extractor_fn: Callable,
    xml_path: str,
    cutoff_date: date,
    fetch_xml: Callable[[str], bytes],
    timeout_seconds: int = SITEMAP_EXTRACTOR_TIMEOUT_SECONDS,
) -> tuple[list[dict], float]:
    """Execute the extractor in a worker thread with a hard timeout.

    Returns (rows, runtime_seconds). Raises on timeout or extractor exception.
    """
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(extractor_fn, xml_path, cutoff_date, fetch_xml)
        try:
            result = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise ExtractorContractError(
                f"Generated extractor exceeded timeout of {timeout_seconds}s."
            ) from exc
    runtime = time.monotonic() - start
    return _validate_extractor_output(result), runtime


def _validate_extractor_output(value) -> list[dict]:
    if not isinstance(value, list):
        raise ExtractorContractError(
            f"Extractor must return a list, got {type(value).__name__}."
        )
    rows: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            raise ExtractorContractError("Extractor list items must be dicts.")
        link = item.get("link", "")
        lastmod = item.get("lastmod", "")
        if not isinstance(link, str) or not link.lower().startswith(("http://", "https://")):
            raise ExtractorContractError(f"Invalid 'link' value in extractor output: {link!r}")
        if not isinstance(lastmod, str):
            raise ExtractorContractError(f"Invalid 'lastmod' value in extractor output: {lastmod!r}")
        rows.append({"link": link, "lastmod": lastmod})
    return rows
