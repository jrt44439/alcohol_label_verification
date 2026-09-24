DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS saved_verifications;

CREATE TABLE products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    brand_name          TEXT,
    class_type          TEXT,
    alcohol_content     TEXT,
    net_contents        TEXT,
    producer_info       TEXT,
    country_of_origin   TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE saved_verifications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_filename     TEXT NOT NULL,
    brand_name          TEXT,
    overall_status      TEXT NOT NULL,
    results_json        TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
