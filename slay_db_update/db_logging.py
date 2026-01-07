import logging
import threading
import psycopg2
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DBHandler(logging.Handler):
    """Logging handler that writes log records into the job_logs table.

    Initializes with a job_id and a psycopg2 connection (log_conn). The handler
    will INSERT into job_logs (job_id, level, message) and commit immediately.
    """
    def __init__(self, job_id: int, conn: psycopg2.extensions.connection, level=logging.NOTSET):
        super().__init__(level)
        self.job_id = int(job_id)
        self.conn = conn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            logger_name = record.name
            file_path = getattr(record, 'pathname', None)
            line_number = getattr(record, 'lineno', None)
            # timestamp as timezone-aware UTC
            ts = datetime.fromtimestamp(getattr(record, 'created', datetime.now().timestamp()), tz=timezone.utc)

            cur = self.conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO job_logs (job_id, logger_name, level, time, file_path, line_number, message) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (self.job_id, logger_name, level, ts, file_path, line_number, msg),
                )
                self.conn.commit()
            finally:
                try:
                    cur.close()
                except Exception as e:
                    self.handleError(record)
        except Exception as e:
            self.handleError(record)
