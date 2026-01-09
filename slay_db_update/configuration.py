from pathlib import Path

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dataclasses import dataclass
from slay_db_update.utils import find_project_root

@dataclass
class Config:
    dsn: str
    start_year: int
    team_ids: list[int]

    def get_session(self):
        if hasattr(self, 'session'):
            return self.session

        conn = self.dsn
        if conn is None:
            raise RuntimeError("database connection string not found in config.yaml")
        engine = create_engine(conn)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        return self.session

    @classmethod
    def from_yaml(cls, path: Path = None) -> 'Config':
        if hasattr(cls,'instance'):
            return cls.instance

        if path is None:
            project_root = find_project_root()
            path = project_root / 'config.yaml'
        if not path.exists():
            raise RuntimeError(f"config.yaml not found at expected path: {path}")

        config_dict = yaml.safe_load(path.read_text())
        cls.instance = cls(
            dsn=config_dict['dsn'],
            start_year=config_dict.get('start_year', 2000),
            team_ids=config_dict.get('team_ids', [])
        )
        return cls.instance

