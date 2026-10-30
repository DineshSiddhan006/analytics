"""Environment configuration. Values are read from .env without overriding process env."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def _load_env() -> None:
    path = ROOT / '.env'
    if path.exists():
        for raw in path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_env()
FABRIC_SERVER = os.getenv('FABRIC_SERVER', '').strip()
FABRIC_DATABASE = os.getenv('FABRIC_DATABASE', '').strip()
FABRIC_TABLE = os.getenv('FABRIC_TABLE', '').strip()
SOURCE_CONNECTION_STRING = os.getenv('SOURCE_CONNECTION_STRING', '').strip()
FABRIC_CONNECT_TIMEOUT = int(os.getenv('FABRIC_CONNECT_TIMEOUT', '180'))
FABRIC_MAX_ROWS = int(os.getenv('FABRIC_MAX_ROWS', '1000000'))
LLM_URL = os.getenv('LLM_URL', '').strip()
LLM_MODEL = os.getenv('LLM_MODEL', 'mistral').strip()
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '240'))
PLAN_STORE_DIR = Path(os.getenv('PLAN_STORE_DIR', str(ROOT / 'data' / 'plans')))

def validate_config() -> None:
    missing = [k for k, v in {'SOURCE_CONNECTION_STRING': SOURCE_CONNECTION_STRING, 'LLM_URL': LLM_URL}.items() if not v]
    if missing:
        raise RuntimeError('Missing required .env settings: ' + ', '.join(missing))
