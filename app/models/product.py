"""Product dataclass and CRUD helpers for the reference-value library."""
from dataclasses import dataclass, fields
from typing import Optional

from app.db import get_db

FIELD_NAMES = (
    "name",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "producer_info",
    "country_of_origin",
)

# The 6 stored fields that document extraction can prefill (excludes "name",
# which is just the user's own label for the saved record).
DOCUMENT_FILLABLE_FIELDS = FIELD_NAMES[1:]

# The 7 label fields that get verified against a photo. "health_warning_text"
# is not a stored product column -- its expected value is always the fixed
# CANONICAL_WARNING constant (see config.py), since the wording never varies.
LABEL_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "producer_info",
    "country_of_origin",
    "health_warning_text",
)


@dataclass
class Product:
    id: int
    name: str
    brand_name: Optional[str]
    class_type: Optional[str]
    alcohol_content: Optional[str]
    net_contents: Optional[str]
    producer_info: Optional[str]
    country_of_origin: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(**{f.name: row[f.name] for f in fields(cls)})


def get_all() -> list[Product]:
    db = get_db()
    rows = db.execute("SELECT * FROM products ORDER BY name COLLATE NOCASE").fetchall()
    return [Product.from_row(r) for r in rows]


def get_by_id(product_id: int) -> Optional[Product]:
    db = get_db()
    row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return Product.from_row(row)


def create(data: dict) -> int:
    db = get_db()
    values = [data.get(f) for f in FIELD_NAMES]
    cur = db.execute(
        f"""INSERT INTO products ({", ".join(FIELD_NAMES)})
            VALUES ({", ".join(["?"] * len(FIELD_NAMES))})""",
        values,
    )
    db.commit()
    return cur.lastrowid


def update(product_id: int, data: dict) -> None:
    db = get_db()
    values = [data.get(f) for f in FIELD_NAMES]
    set_clause = ", ".join(f"{f} = ?" for f in FIELD_NAMES)
    db.execute(
        f"UPDATE products SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values + [product_id],
    )
    db.commit()


def delete(product_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
