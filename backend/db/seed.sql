-- FinAlly default seed data (PLAN.md §7).
-- Timestamps are generated as UTC ISO-8601 (Z-suffixed) to match the format the
-- backend writes at runtime. INSERT OR IGNORE keeps seeding idempotent.

INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at)
VALUES ('default', 10000.0, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));

INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b01', 'default', 'AAPL',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b02', 'default', 'GOOGL', strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b03', 'default', 'MSFT',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b04', 'default', 'AMZN',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b05', 'default', 'TSLA',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b06', 'default', 'NVDA',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b07', 'default', 'META',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b08', 'default', 'JPM',   strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b09', 'default', 'V',     strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('9f1c0a2e-6b7d-4e21-a3f0-0d1e2f3a4b10', 'default', 'NFLX',  strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
