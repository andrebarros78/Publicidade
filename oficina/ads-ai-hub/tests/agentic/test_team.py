import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic.runtime.team import posts, owner_controls

def test_team_has_all_posts():
    p = posts(); assert len(p) == 16; assert len({x.id for x in p}) == 16
def test_required_experts_present():
    ids = {x.id for x in posts()}
    required = {'chief_ads_officer','marketing_strategist','market_intelligence','consumer_intelligence','performance_scientist','marketing_science','budget_allocator','creative_director','meta_media_buyer','tiktok_media_buyer','risk_guardian'}
    assert required <= ids
def test_owner_does_not_own_strategy():
    c=owner_controls(); assert 'strategy' in c['system_owns']; assert 'monthly_spend_ceiling' in c['owner_defines']
def test_agents_cannot_raise_ceiling():
    assert 'increase_owner_spend_ceiling' in owner_controls()['never_autonomous']
def test_contracts_parse():
    for p in (ROOT/'agentic'/'contracts').glob('*.json'): json.loads(p.read_text(encoding='utf-8'))
