from logging import Logger
from logging.config import dictConfig
from pathlib import Path
from typing import Optional, Callable, Any

import psycopg2
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dataclasses import dataclass, field
from slay_db_update.utils import find_project_root
import logging
from typing import TypeAlias

LoggerFactory: TypeAlias = Callable[[str], Logger]
@dataclass
class Config:
    dsn: str
    start_year: int
    team_ids: list[int]
    logger_factory: LoggerFactory = lambda name: logging.getLogger(name)
    session: Session = field(init = False)
    db_connection: Any = field(init=False)

    def __post_init__(self):
        conn_string = self.dsn
        if conn_string is None:
            raise RuntimeError("database connection string not found in config.yaml")
        engine = create_engine(conn_string)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        self.db_connection = self.create_db_connection()

    def wrap_logger_factory(self, decorator: Callable[[LoggerFactory], LoggerFactory]) -> LoggerFactory:
        setattr(decorator, 'wrapped', self.logger_factory)
        self.logger_factory = decorator(self.logger_factory)
        return self.logger_factory

    def unwrap_logger_factory(self) -> LoggerFactory:
        if hasattr(self.logger_factory, 'wrapped'):
            wrapped = getattr(self.logger_factory, 'wrapped')
            delattr(self.logger_factory, 'wrapped')
            self.logger_factory = wrapped
        return self.logger_factory

    def create_db_connection(self):
        return psycopg2.connect(self.dsn)

        return self.connection
    @staticmethod
    def read_logging_config():
        cfg_path = Path(__file__).resolve().parents[2] / 'logging.yaml'
        if not cfg_path.exists():
            # fallback to project root logging.yaml
            cfg_path = Path.cwd() / 'logging.yaml'
        if cfg_path.exists():
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f)
            # convert YAML logging config format into dictConfig format
            dictConfig(cfg)

    def get_logger(self, name: str):
        Config.read_logging_config()
        if self.logger_factory is None:
            raise ("logger_factory not defined")
        return self.logger_factory(name)

    def get_session(self):
        if self.session is not None:
            return self.session

        conn = self.dsn
        if conn is None:
            raise RuntimeError("database connection string not found in config.yaml")
        engine = create_engine(conn)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        return self.session

    @classmethod
    def get(cls, path: Path = None) -> 'Config':
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

