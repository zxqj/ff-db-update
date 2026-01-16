# shim for backward compatibility: re-export the decorator from conf.job_tracker
from slay_db_update.conf.job_tracker import track_job

# Preserve the old symbol name
job_runner = track_job
