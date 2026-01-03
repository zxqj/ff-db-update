-- V4: create script_executions table (run against the 'nba' database)

CREATE TABLE IF NOT EXISTS script_executions (
    name            TEXT NOT NULL,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,
    status          TEXT NOT NULL CHECK (status IN ('completed','failed','running')),
    error_message   TEXT,
    comments        TEXT
);

-- Optional: prevent duplicate runs for same script at the same start time
CREATE UNIQUE INDEX IF NOT EXISTS idx_script_executions_name_start_time ON script_executions (name, start_time);
