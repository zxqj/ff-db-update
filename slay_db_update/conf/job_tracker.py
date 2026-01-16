import functools
import logging
from typing import Callable, Any
from slay_db_update.conf import Config
from slay_db_update.conf.db_logging import DBHandler
from slay_db_update.utils import describe_exception


def track_job(job_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
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
            # Create separate connections so logging always commits independently
            log_conn = Config.get().create_db_connection()
            app_conn = Config.get().db_connection


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
                    def logger_factory_decorator(wrapped_factory: Callable[[str], logging.Logger]) -> Callable[[str], logging.Logger]:
                        # create logger factory bound to this job_id and log_conn
                        def logger_factory(module_name: str):
                            # get module logger
                            lg = wrapped_factory(module_name)
                            # attach DBHandler which uses the same log_conn
                            handler = DBHandler(job_id=job_id, conn=log_conn, level=logging.DEBUG)
                            # use a simple formatter; modules may override
                            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                            lg.addHandler(handler)
                            return lg
                        return logger_factory

                    job_logger_factory = Config.get().wrap_logger_factory(logger_factory_decorator)
                    result = func(*args, **kwargs)

                    Config.get().unwrap_logger_factory()
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
                    logger = job_logger_factory(func.__module__)
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

        return wrapper

    return decorator

