from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from agents import Agent, handoff
from agentic.runtime.team import posts

@dataclass(frozen=True)
class RuntimeTeam:
    chief: Agent
    agents: dict[str, Agent]

BASE_RULES = '''
Operate only inside the owner's monthly spend ceiling and hard business constraints.
Never change payment methods, account ownership, or irreversibly delete important assets.
Base decisions on evidence and structured metrics. Prefer reversible bounded experiments.
Strategy, audience, creatives, channel mix and internal allocation belong to the agent team.
'''

SPECIALIST_INSTRUCTIONS = {
    'marketing_strategist': 'Own positioning, funnel, offers, channel strategy and integrated marketing plan.',
    'market_intelligence': 'Analyze competitors, demand, market signals, seasonality and opportunities.',
    'consumer_intelligence': 'Analyze consumer behavior, segments, audiences, saturation and targeting hypotheses.',
    'product_portfolio': 'Rank products using margin, stock, conversion, demand, ticket and advertising economics.',
    'performance_scientist': 'Read performance metrics statistically; detect trends, anomalies and causal hypotheses.',
    'marketing_science': 'Own MMM and cross-channel measurement; use Meridian/Robyn outputs when available.',
    'attribution_specialist': 'Analyze attribution and incrementality; separate correlation from causal lift.',
    'budget_allocator': 'Redistribute budget across channels/campaigns without ever increasing owner ceiling.',
    'experiment_scientist': 'Design bounded tests with hypotheses, primary metrics, stopping rules and max loss.',
    'creative_director': 'Own creative strategy, fatigue detection, concepts and testing roadmap.',
    'copywriter': 'Produce and test direct-response copy, hooks, offers and CTAs within brand constraints.',
    'meta_media_buyer': 'Operate Meta Ads through approved ADS-AI-HUB tools and policy.',
    'tiktok_media_buyer': 'Operate TikTok Ads through approved ADS-AI-HUB tools and policy.',
    'risk_guardian': 'Veto actions that breach spend ceiling, safety, duplication, reversibility or policy.',
    'ads_operations': 'Own audit trail, retries, recovery, observability and operational integrity.'
}

def build_team(model: str = 'gpt-5.6') -> RuntimeTeam:
    registry = {p.id: p for p in posts()}
    specialists: dict[str, Agent] = {}
    for agent_id, instr in SPECIALIST_INSTRUCTIONS.items():
        post = registry[agent_id]
        specialists[agent_id] = Agent(
            name=post.title,
            handoff_description=instr,
            instructions=BASE_RULES + '\n' + instr,
            model=model,
        )

    strategy = specialists['marketing_strategist']
    strategy.handoffs = [
        specialists['market_intelligence'], specialists['consumer_intelligence'],
        specialists['creative_director']
    ]
    specialists['creative_director'].handoffs = [specialists['copywriter']]
    specialists['performance_scientist'].handoffs = [
        specialists['marketing_science'], specialists['attribution_specialist'],
        specialists['experiment_scientist']
    ]

    chief_targets = [
        strategy,
        specialists['product_portfolio'],
        specialists['performance_scientist'],
        specialists['budget_allocator'],
        specialists['meta_media_buyer'],
        specialists['tiktok_media_buyer'],
        specialists['risk_guardian'],
        specialists['ads_operations'],
    ]
    chief = Agent(
        name=registry['chief_ads_officer'].title,
        instructions=BASE_RULES + '''\nYou are accountable for the whole advertising operation. Delegate to specialists, synthesize evidence, and choose the best actions. The owner should not need to design strategy.''',
        model=model,
        handoffs=[handoff(a) for a in chief_targets],
    )
    return RuntimeTeam(chief=chief, agents={'chief_ads_officer': chief, **specialists})
