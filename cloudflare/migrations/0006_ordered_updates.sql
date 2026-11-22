-- Keep per-user command order without blocking unrelated chats.
ALTER TABLE telegram_update ADD COLUMN actor_id TEXT GENERATED ALWAYS AS
  (CAST(COALESCE(json_extract(payload, '$.callback_query.from.id'), json_extract(payload, '$.message.from.id')) AS TEXT)) VIRTUAL;
CREATE INDEX ordered_updates ON telegram_update(actor_id, status, id);

-- The final write in a processing batch fences an expired worker. A newer lease
-- increments attempts; aborting the batch rolls back all of the stale worker's writes.
CREATE TRIGGER fence_update_completion BEFORE UPDATE OF status ON telegram_update
WHEN NEW.status = 'done' AND (NEW.attempts != OLD.attempts
  OR OLD.status != 'pending' OR OLD.lease_until <= unixepoch())
BEGIN SELECT RAISE(ABORT, 'update lease superseded'); END;

ALTER TABLE outbox ADD COLUMN subscription_id TEXT REFERENCES user_sub_good(id);
-- Legacy price alerts have no subscription association. Expire them once;
-- command replies (priority 0) remain deliverable.
UPDATE outbox SET sent_at = -1 WHERE sent_at IS NULL AND priority = 1;
CREATE INDEX outbox_subscription ON outbox(subscription_id, sent_at);
