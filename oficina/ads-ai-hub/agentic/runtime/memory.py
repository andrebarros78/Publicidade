import json
from pathlib import Path
from datetime import datetime, timezone

class AuditMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict) -> None:
        record = {'ts': datetime.now(timezone.utc).isoformat(), **event}
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')

    def read(self) -> list[dict]:
        if not self.path.exists(): return []
        return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines() if x.strip()]
