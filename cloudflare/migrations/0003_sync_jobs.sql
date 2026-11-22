CREATE TABLE sync_job (
    slot INTEGER PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    next_attempt INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
ALTER TABLE outbox ADD COLUMN priority INTEGER NOT NULL DEFAULT 1;
DROP INDEX pending_outbox;
CREATE INDEX pending_outbox ON outbox(sent_at, priority, created_at, next_attempt);
