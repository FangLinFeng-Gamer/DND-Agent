import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = Path(os.environ.get("DND_AGENT_DB_PATH", PROJECT_ROOT / "data" / "dnd_agent.sqlite3"))
DEFAULT_STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
