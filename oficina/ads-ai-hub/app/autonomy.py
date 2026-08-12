from fastapi import APIRouter, Query
from agentic.runtime.team import posts, owner_controls
from agentic.digital_twin.engine import DigitalTwin

router = APIRouter(prefix='/v1/autonomy', tags=['autonomy'])

@router.get('/team')
def team():
    return {'agents':[p.__dict__ for p in posts()], 'controls':owner_controls()}

@router.post('/digital-twin')
def digital_twin(monthly_spend_ceiling: float = Query(10000, ge=0)):
    twin=DigitalTwin(monthly_spend_ceiling)
    return twin.cycle()
