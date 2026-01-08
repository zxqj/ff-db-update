from pathlib import Path

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from slay_db_update.utils import find_project_root


def _get_db_session(config_path=None):
    if config_path:
        cfg_path = Path(config_path)
    else:
        project_root = find_project_root()
        cfg_path = project_root / 'config.yaml'
    if not cfg_path.exists():
        raise RuntimeError(f"config.yaml not found at expected path: {cfg_path}")
    cfg = yaml.safe_load(cfg_path.read_text())
    conn = cfg.get('dsn')
    if conn is None:
        raise RuntimeError("database connection string not found in config.yaml")
    engine = create_engine(conn)
    Session = sessionmaker(bind=engine)
    return Session()
