import click
from .cli_tools import loudspeaker, wrap_module_with_decorator
from .configuration import Config
from .players import update as players_update
from .games import update as games_update
import functools
from pathlib import Path
import psycopg2
from typing import Any, Callable
import logging
from logging.config import dictConfig
from .db_logging import DBHandler

import yaml as _yaml

from .utils import describe_exception

loud_sh = wrap_module_with_decorator('sh', loudspeaker)


def _read_dsn() -> str:
    """Read the `dsn` value from the project root `config.yaml`.
    Returns the DSN string or raises a RuntimeError if not found.
    """
    # config.yaml lives at the project root (two levels up from this file)
    possible_paths = [
        Path(__file__).resolve().parents[1] / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    for p in possible_paths:
        if p.exists():
            with p.open() as f:
                data = _yaml.safe_load(f)
                if isinstance(data, dict) and "dsn" in data:
                    return data["dsn"]
    raise RuntimeError("dsn not found in config.yaml")


def job_runner(job_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that logs script execution to the `jobs` table.

    Behavior:
    - Creates two DB connections using the DSN from config.yaml: one for logging
      (log_conn) and one for the transactional work (app_conn).
    - Inserts a row into `jobs` with status 'running' and start_time = now().
    - Passes the transactional connection to the wrapped function via the keyword
      argument `db_conn` (unless already provided).
    - On success commits the transaction and updates the row to status 'completed' and sets end_time.
    - On exception rolls back the transaction, updates the row to status 'failed' and records the error_message,
      then re-raises the exception.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            dsn = _read_dsn()
            # Create separate connections so logging always commits independently
            log_conn = psycopg2.connect(dsn)
            app_conn = psycopg2.connect(dsn)
            try:
                # Configure global logging from logging.yaml at decorator start
                # (load once per decorator invocation)
                try:
                    cfg_path = Path(__file__).resolve().parents[2] / 'logging.yaml'
                    if not cfg_path.exists():
                        # fallback to project root logging.yaml
                        cfg_path = Path.cwd() / 'logging.yaml'
                    if cfg_path.exists():
                        with cfg_path.open() as f:
                            cfg = _yaml.safe_load(f)
                        # convert YAML logging config format into dictConfig format
                        dictConfig(cfg)
                except Exception:
                    # If logging config fails, continue with default logging
                    logging.basicConfig()

                try:
                    log_cur = log_conn.cursor()
                    # Insert running record and capture start_time
                    log_cur.execute(
                        "INSERT INTO jobs (job_type, start_time, status, comments) VALUES (%s, now(), %s, %s) RETURNING id, start_time",
                        (job_type, 'running', None),
                    )
                    job_row = log_cur.fetchone()
                    job_id = job_row[0]
                    start_time = job_row[1]
                    log_conn.commit()

                    try:
                        # Begin transactional work for wrapped function
                        app_conn.autocommit = False
                        if 'db_conn' not in kwargs:
                            kwargs['db_conn'] = app_conn

                        # create logger factory bound to this job_id and log_conn
                        def logger_factory(module_name: str):
                            # get module logger
                            lg = logging.getLogger(module_name)
                            # attach DBHandler which uses the same log_conn
                            handler = DBHandler(job_id=job_id, conn=log_conn, level=logging.DEBUG)
                            # use a simple formatter; modules may override
                            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                            lg.addHandler(handler)
                            return lg

                        Config.get().set_logger_factory(logger_factory)

                        if 'logger_factory' not in kwargs:
                            kwargs['logger_factory'] = logger_factory

                        result = func(*args, **kwargs)
                        # If the wrapped function completed, commit
                        app_conn.commit()

                        # Update logging row to completed
                        log_cur.execute(
                            "UPDATE jobs SET end_time = now(), status = %s WHERE id = %s",
                            ('completed', job_id),
                        )
                        log_conn.commit()
                        return result
                    except Exception as exc:
                        # Rollback transactional work
                        app_conn.rollback()
                        # Record failure and the error message (truncate if necessary)
                        err_text = describe_exception(exc)
                        logger = logger_factory(func.__module__)
                        logger.error(err_text)
                        if len(err_text) > 2000:
                            err_text = err_text[:2000]
                        log_cur.execute(
                            "UPDATE jobs SET end_time = now(), status = %s, error_message = %s WHERE id = %s",
                            ('failed', err_text, job_id),
                        )
                        log_conn.commit()
                        raise
                finally:
                    try:
                        log_conn.close()
                    except Exception:
                        pass
                    try:
                        app_conn.close()
                    except Exception:
                        pass
            except Exception:
                pass
            
        return wrapper

    return decorator


@click.group()
@click.version_option()
def cli():
    """
    """


@cli.command(name="players")
@job_runner("players")
def players(*args, **kwargs):
    players_update(*args, **kwargs)


@cli.command(name="games")
@job_runner("player_games")
def games(*args, **kwargs):
    """Wrapper command that calls the `games_update` function in `games.py`.

    The real work is implemented in `slay_db_update.games.update(db_conn)` so it can
    be imported and tested independently from the CLI. The decorator supplies the
    transactional `db_conn` argument.
    """
    print("asdf")
    inserted = games_update(*args, **kwargs)
    click.echo(str(inserted))
