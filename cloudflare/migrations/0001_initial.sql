PRAGMA foreign_keys = ON;

CREATE TABLE "user" (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    state INTEGER NOT NULL DEFAULT 1 CHECK (state IN (0, 1)),
    pending_action TEXT,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE good_info (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price > 0),
    stock_state INTEGER NOT NULL CHECK (stock_state IN (0, 1, 2)),
    state INTEGER NOT NULL DEFAULT 1 CHECK (state IN (0, 1)),
    version INTEGER NOT NULL DEFAULT 0,
    next_check INTEGER NOT NULL DEFAULT 0,
    last_success INTEGER,
    last_error TEXT,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE user_sub_good (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES "user"(id),
    good_id TEXT NOT NULL REFERENCES good_info(id),
    price INTEGER NOT NULL CHECK (price > 0),
    is_notified INTEGER NOT NULL DEFAULT 0 CHECK (is_notified IN (0, 1)),
    state INTEGER NOT NULL DEFAULT 1 CHECK (state IN (0, 1)),
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, good_id)
);
CREATE INDEX subscriptions_user ON user_sub_good(user_id, state);
CREATE INDEX subscriptions_good ON user_sub_good(good_id, state);
CREATE INDEX due_goods ON good_info(state, next_check);

CREATE TABLE telegram_update (
    id INTEGER PRIMARY KEY,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    lease_until INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE INDEX pending_updates ON telegram_update(status, lease_until);
CREATE TABLE outbox (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES "user"(id),
    payload TEXT NOT NULL,
    next_attempt INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    sent_at INTEGER
);
CREATE INDEX pending_outbox ON outbox(sent_at, next_attempt);

