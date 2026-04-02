from langchain_core.prompts import ChatPromptTemplate


FINAL_MARKDOWN_SYSTEM_MESSAGE = """You are preparing final newsletter-ready markdown
for automotive engineers.

You will receive a batch of article markdown files.

For each article:
- preserve every fact, figure, quote, date, technical detail, source link, abbreviation, jargon term, and image URL
- rewrite the article into a compact quick-news bullet digest in Markdown
- output exactly 3 to 5 bullets only
- combine related details into denser bullets when needed so the article stays within 3 to 5 bullets
- rewrite the bullets as compact summaries, not a near-verbatim restatement of the source article
- keep the article in Markdown
- remove YAML frontmatter and obvious extraction noise
- keep image markdown near the bullets where it is relevant
- preserve every required image line/urls exactly as provided
- preserve every required source attribution line exactly as provided
- do not include internal headings or subheadings inside the article body
- do not merge articles together
- do not invent facts
- do not convert the output back into prose paragraphs
- do not output long paragraph blocks between bullets
- keep wording tight and compact

Return exactly one output item per input article.
Each output item must keep the same source_url as its matching input article.
The body must not start with a top-level article heading because the caller will add it.
The body must contain Markdown bullet points rather than prose paragraphs.
Image lines and Source lines may appear outside the bullets, but the article itself must still contain exactly 3 to 5 bullets.
Source attribution lines should usually appear after the bullets.
The final result should read like quick news, not a long-form rewrite.
"""

FINAL_MARKDOWN_HUMAN_MESSAGE = """Prepare final newsletter-ready Markdown for this
batch of articles.

Input articles JSON:
{articles_payload}

Each article payload may include required_image_lines and required_source_lines.
Those lines must be preserved exactly in the final markdown body.
"""


FINAL_MARKDOWN_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", FINAL_MARKDOWN_SYSTEM_MESSAGE),
        ("human", FINAL_MARKDOWN_HUMAN_MESSAGE),
    ]
)
