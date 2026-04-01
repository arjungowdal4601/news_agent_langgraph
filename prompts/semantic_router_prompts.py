from langchain_core.prompts import ChatPromptTemplate


SEMANTIC_ROUTER_SYSTEM_MESSAGE = """You are a semantic router.
Your only job is to judge relevance.
Assign a similarity score from 0 to 100.
Decide selected true or false.
Return one short reason.
Do not invent facts.
Judge only from the provided markdown.
"""


SEMANTIC_ROUTER_HUMAN_MESSAGE = """User need:
{user_need}

Source URL:
{source_url}

Markdown content:
{markdown_content}
"""


SEMANTIC_ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SEMANTIC_ROUTER_SYSTEM_MESSAGE),
        ("human", SEMANTIC_ROUTER_HUMAN_MESSAGE),
    ]
)


USER_NEED = """
Task:
Judge whether this article is meaningfully relevant to automotive R&D and engineering work.

How to think:
- Reward articles that are genuinely useful to an automotive R&D, engineering, validation, software, systems, battery, ADAS, semiconductor, or platform team.
- Reward technical depth, engineering detail, architecture implications, validation implications, safety implications, and technology impact.
- Reward articles about technical bottlenecks or engineering risks if they materially affect development, readiness, validation, cost, or system design.
- Do not reward articles just because they sound futuristic.
- Do not reward articles just because they mention jargons like  AI, EV, software, autonomy, or battery once study the actual content.
- An article can be relevant even if it is about a technical issue, shortage, validation challenge, safety risk, or architecture tradeoff.
- Judge only from the provided markdown content. Do not invent missing details.

What does NOT count as relevant:
- sales, demand, pricing, discounts, market share, revenue, profit, exports, deliveries
- general auto industry business news
- plant openings or partnerships with no real engineering substance
- normal car launches, facelifts, refreshes, or product announcements
- spec-heavy articles that just list range, power, acceleration, or features
- ordinary infotainment or feature updates unless they reflect a deeper architecture or engineering shift
- routine EV/ADAS coverage without meaningful technical depth
- vehicle reviews, first drives, comparisons, or buying advice

Scoring guide:
- 0 to 20: irrelevant to automotive R&D
- 21 to 40: weak or indirect relevance
- 41 to 60: relevant topic but shallow or low engineering value
- 61 to 80: clearly relevant to automotive R&D with useful engineering substance
- 81 to 100: strongly relevant, high-signal engineering/R&D article

Selection rule:
- selected = true only if the article is meaningfully useful for automotive R&D or engineering-focused reporting score id above 70
- selected = false otherwise

Return:
- similarity_score: integer from 0 to 100
- selected: true or false
- reason: one short clear reason
"""
