"""Persisted COLA verification results. A saved record captures the same
per-field summary and per-photo detail the live batch results page shows --
raw OCR text included, for later audit -- but never the photo images
themselves."""
import json
from dataclasses import dataclass
from typing import Optional

from app.db import get_db

_LIST_COLUMNS = ("id", "source_filename", "brand_name", "overall_status", "created_at", "updated_at")


@dataclass
class SavedVerificationSummary:
    id: int
    source_filename: str
    brand_name: Optional[str]
    overall_status: str
    created_at: str
    updated_at: str


@dataclass
class SavedVerification:
    id: int
    source_filename: str
    brand_name: Optional[str]
    overall_status: str
    field_summary: dict
    warning_caps_ok: Optional[bool]
    warning_bold_ok: Optional[bool]
    photos: list
    created_at: str
    updated_at: str


def _overall_status(field_summary: dict) -> str:
    if field_summary and all(v.get("status") == "match" for v in field_summary.values()):
        return "pass"
    return "needs_review"


def _brand_name_for_display(field_summary: dict) -> Optional[str]:
    brand = field_summary.get("brand_name", {})
    return brand.get("value") or brand.get("expected")


def _encode_results(field_summary: dict, warning_caps_ok, warning_bold_ok, photos: list) -> str:
    return json.dumps(
        {
            "field_summary": field_summary,
            "warning_caps_ok": warning_caps_ok,
            "warning_bold_ok": warning_bold_ok,
            "photos": photos,
        }
    )


def get_all() -> list[SavedVerificationSummary]:
    db = get_db()
    rows = db.execute(
        "SELECT id, source_filename, brand_name, overall_status, created_at, updated_at "
        "FROM saved_verifications ORDER BY created_at DESC"
    ).fetchall()
    return [SavedVerificationSummary(**{k: r[k] for k in _LIST_COLUMNS}) for r in rows]


def get_by_id(verification_id: int) -> Optional[SavedVerification]:
    db = get_db()
    row = db.execute("SELECT * FROM saved_verifications WHERE id = ?", (verification_id,)).fetchone()
    if row is None:
        return None
    payload = json.loads(row["results_json"])
    return SavedVerification(
        id=row["id"],
        source_filename=row["source_filename"],
        brand_name=row["brand_name"],
        overall_status=row["overall_status"],
        field_summary=payload["field_summary"],
        warning_caps_ok=payload.get("warning_caps_ok"),
        warning_bold_ok=payload.get("warning_bold_ok"),
        photos=payload.get("photos", []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create(source_filename: str, field_summary: dict, warning_caps_ok, warning_bold_ok, photos: list) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO saved_verifications (source_filename, brand_name, overall_status, results_json) "
        "VALUES (?, ?, ?, ?)",
        (
            source_filename,
            _brand_name_for_display(field_summary),
            _overall_status(field_summary),
            _encode_results(field_summary, warning_caps_ok, warning_bold_ok, photos),
        ),
    )
    db.commit()
    return cur.lastrowid


def update(verification_id: int, field_summary: dict, warning_caps_ok, warning_bold_ok, photos: list) -> None:
    db = get_db()
    db.execute(
        "UPDATE saved_verifications SET brand_name = ?, overall_status = ?, results_json = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (
            _brand_name_for_display(field_summary),
            _overall_status(field_summary),
            _encode_results(field_summary, warning_caps_ok, warning_bold_ok, photos),
            verification_id,
        ),
    )
    db.commit()


def delete(verification_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM saved_verifications WHERE id = ?", (verification_id,))
    db.commit()
