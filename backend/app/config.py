from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path("/app/data") if Path("/app/data").exists() else APP_DIR.parent / "data"
PROJECTS_DIR = DATA_DIR / "projects"
DB_PATH = DATA_DIR / "app.db"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
