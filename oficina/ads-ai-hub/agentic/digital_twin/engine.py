from __future__ import annotations
from dataclasses import dataclass, asdict
from agentic.runtime.spend_guard import check_spend

@dataclass
class Campaign:
    id: str
    platform: str
    spend: float
    revenue: float
    cpa: float
    ctr: float
    frequency: float
    status: str = 'active'

    @property
    def roas(self): return 0.0 if self.spend == 0 else self.revenue / self.spend

class DigitalTwin:
    def __init__(self, ceiling: float):
        self.ceiling = ceiling
        self.campaigns = [
            Campaign('meta-winner','meta',2400,14400,28,2.8,2.1),
            Campaign('meta-fatigue','meta',1300,2600,72,0.7,5.9),
            Campaign('tiktok-growth','tiktok',900,5400,31,2.4,1.8),
            Campaign('tiktok-loss','tiktok',700,350,115,0.5,3.7),
        ]
        self.audit = []

    def total_spend(self): return sum(c.spend for c in self.campaigns)

    def cycle(self):
        actions=[]
        # Performance + creative diagnosis
        for c in self.campaigns:
            if c.roas < 1.0 or c.cpa > 100:
                c.status='paused'; actions.append({'agent':'performance_scientist','action':'pause','campaign':c.id,'reason':'loss'})
            elif c.frequency > 5 and c.ctr < 1:
                actions.append({'agent':'creative_director','action':'refresh_creative','campaign':c.id,'reason':'fatigue'})
        # Budget allocator: shift a bounded R$300 from weak Meta to best performer without raising ceiling
        active=[c for c in self.campaigns if c.status=='active']
        best=max(active,key=lambda c:c.roas)
        donor=min(active,key=lambda c:c.roas)
        transfer=min(300.0, donor.spend*0.15)
        donor.spend-=transfer
        guard=check_spend(spent=self.total_spend(), proposed_increment=transfer, ceiling=self.ceiling)
        if guard.allowed:
            best.spend+=transfer
            actions.append({'agent':'budget_allocator','action':'transfer','from':donor.id,'to':best.id,'amount':transfer})
        else:
            donor.spend+=transfer
            actions.append({'agent':'risk_guardian','action':'veto','reason':guard.reason})
        self.audit.extend(actions)
        return {'ceiling':self.ceiling,'spend':self.total_spend(),'campaigns':[asdict(c)|{'roas':round(c.roas,3)} for c in self.campaigns],'actions':actions}
