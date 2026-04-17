"""LangGraph node that prepares a per-site sitemap extractor.

Sits between download_xml and extract_urls_to_excel. It calls
load_or_generate_extractor() to either reuse a cached extractor script or
generate a fresh one with the LLM, then records the cache path on state so
the extractor node can run it.
"""

from datetime import date

from constants import SITEMAP_EXTRACTOR_FORCE_REGENERATE
from services.path_service import get_site_name
from services.sitemap_extractor_agent_service import (
    ExtractorContractError,
    load_or_generate_extractor,
)
from state import PipelineState


def generate_sitemap_extractor(state: PipelineState) -> dict:
    """Load or generate the per-site extractor script.

    Returns updates for `extractor_script_path` and `extractor_source`.
    On any failure the keys are still returned (with empty path) so the
    downstream node can detect the absence and fall back to the generic
    walker.
    """
    base_url = state["base_url"]
    site_name = get_site_name(base_url)
    cutoff = date.fromisoformat(state["cutoff_date"])

    try:
        _fn, source_tag, sample_digest, cache_file = load_or_generate_extractor(
            site_name=site_name,
            xml_path=state["xml_file_path"],
            cutoff_date=cutoff,
            force=SITEMAP_EXTRACTOR_FORCE_REGENERATE,
        )
        print(
            f"{site_name}: extractor ready ({source_tag}, sample_hash={sample_digest}) "
            f"-> {cache_file}"
        )
        return {
            "extractor_script_path": str(cache_file.resolve()),
            "extractor_source": source_tag,
        }
    except (ExtractorContractError, ValueError) as exc:
        print(f"{site_name}: extractor generation failed ({exc}); falling back to walker.")
        return {
            "extractor_script_path": "",
            "extractor_source": "fallback",
        }
