DROP TABLE IF EXISTS products;

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
