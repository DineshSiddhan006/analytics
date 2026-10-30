"""Per-table JSON persistence for approved, edited and rejected analytics."""
from __future__ import annotations
import copy, json, os, re, tempfile, threading
from pathlib import Path
from datetime import datetime, timezone

class JsonPlanStore:
    def __init__(self, directory): self.directory = Path(directory); self.lock = threading.RLock()
    def path(self, table): return self.directory / (re.sub(r'[^A-Za-z0-9_.-]+','_',table)+'.json')
    def load(self, table):
        p = self.path(table)
        with self.lock:
            if not p.exists(): return {'schema_version':1,'table':table,'approved':[],'edited':[],'rejected':[]}
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                if data.get('schema_version') != 1: raise ValueError('Unsupported plan JSON version')
                data.setdefault('approved',[]); data.setdefault('edited',[]); data.setdefault('rejected',[])
                return data
            except Exception as exc: raise RuntimeError(f'Cannot read saved analytics decisions {p}: {exc}') from exc
    def save(self, table, state):
        payload = copy.deepcopy(state); payload.update({'schema_version':1,'table':table,'updated_at':datetime.now(timezone.utc).isoformat()})
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock:
            fd, tmp = tempfile.mkstemp(prefix='.'+self.path(table).name, suffix='.tmp', dir=self.directory)
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(payload,f,indent=2,ensure_ascii=False,default=str); f.flush(); os.fsync(f.fileno())
                os.replace(tmp,self.path(table))
            except BaseException:
                try: os.unlink(tmp)
                except OSError: pass
                raise
