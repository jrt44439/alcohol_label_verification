"""Per-field comparison logic between OCR-extracted label values and the
user's expected/reference values."""
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz

from app.comparison.normalize import normalize_abv, normalize_text, normalize_volume


class MatchStatus(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_FOUND = "not_found"


@dataclass
class FieldComparison:
    field_key: str
    display_name: str
    extracted_value: str | None
    expected_value: str | None
    status: MatchStatus
    score: float | None = None


FIELD_DISPLAY_NAMES = {
    "brand_name": "Brand Name",
    "class_type": "Class / Type",
    "alcohol_content": "Alcohol Content",
    "net_contents": "Net Contents",
    "producer_info": "Producer / Bottler / Importer",
    "country_of_origin": "Country of Origin",
    "health_warning_text": "Government Health Warning",
}


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def compare_text_field(
    field_key: str, extracted: str | None, expected: str | None, threshold: float
) -> FieldComparison:
    display_name = FIELD_DISPLAY_NAMES[field_key]

    if _is_blank(extracted):
        status = MatchStatus.MATCH if _is_blank(expected) else MatchStatus.NOT_FOUND
        return FieldComparison(field_key, display_name, extracted, expected, status, None)

    if _is_blank(expected):
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.MATCH, None)

    score = fuzz.token_sort_ratio(normalize_text(extracted), normalize_text(expected))
    status = MatchStatus.MATCH if score >= threshold else MatchStatus.MISMATCH
    return FieldComparison(field_key, display_name, extracted, expected, status, score)


def compare_warning_field(
    extracted: str | None, expected: str | None, threshold: float
) -> FieldComparison:
    field_key = "health_warning_text"
    display_name = FIELD_DISPLAY_NAMES[field_key]

    if _is_blank(extracted):
        status = MatchStatus.MATCH if _is_blank(expected) else MatchStatus.NOT_FOUND
        return FieldComparison(field_key, display_name, extracted, expected, status, None)

    if _is_blank(expected):
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.MATCH, None)

    score = fuzz.partial_ratio(normalize_text(extracted), normalize_text(expected))
    status = MatchStatus.MATCH if score >= threshold else MatchStatus.MISMATCH
    return FieldComparison(field_key, display_name, extracted, expected, status, score)


def compare_abv_field(
    extracted: str | None, expected: str | None, tolerance: float
) -> FieldComparison:
    field_key = "alcohol_content"
    display_name = FIELD_DISPLAY_NAMES[field_key]

    if _is_blank(extracted):
        status = MatchStatus.MATCH if _is_blank(expected) else MatchStatus.NOT_FOUND
        return FieldComparison(field_key, display_name, extracted, expected, status, None)

    if _is_blank(expected):
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.MATCH, None)

    pct_x, _ = normalize_abv(extracted)
    pct_e, _ = normalize_abv(expected)

    if pct_x is None or pct_e is None:
        # Couldn't parse a numeric percentage from one side; fall back to fuzzy text.
        score = fuzz.token_sort_ratio(normalize_text(extracted), normalize_text(expected))
        status = MatchStatus.MATCH if score >= 85 else MatchStatus.MISMATCH
        return FieldComparison(field_key, display_name, extracted, expected, status, score)

    diff = abs(pct_x - pct_e)
    status = MatchStatus.MATCH if diff <= tolerance else MatchStatus.MISMATCH
    score = max(0.0, 100.0 - diff * 10)
    return FieldComparison(field_key, display_name, extracted, expected, status, score)


def compare_volume_field(
    extracted: str | None, expected: str | None, tolerance_pct: float
) -> FieldComparison:
    field_key = "net_contents"
    display_name = FIELD_DISPLAY_NAMES[field_key]

    if _is_blank(extracted):
        status = MatchStatus.MATCH if _is_blank(expected) else MatchStatus.NOT_FOUND
        return FieldComparison(field_key, display_name, extracted, expected, status, None)

    if _is_blank(expected):
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.MATCH, None)

    ml_x = normalize_volume(extracted)
    ml_e = normalize_volume(expected)

    if ml_x is None or ml_e is None:
        score = fuzz.token_sort_ratio(normalize_text(extracted), normalize_text(expected))
        status = MatchStatus.MATCH if score >= 85 else MatchStatus.MISMATCH
        return FieldComparison(field_key, display_name, extracted, expected, status, score)

    pct_diff = abs(ml_x - ml_e) / ml_e * 100 if ml_e else 100.0
    status = MatchStatus.MATCH if pct_diff <= tolerance_pct else MatchStatus.MISMATCH
    score = max(0.0, 100.0 - pct_diff)
    return FieldComparison(field_key, display_name, extracted, expected, status, score)


def compare_product(
    extracted_fields: dict[str, str | None],
    expected_fields: dict[str, str | None],
    text_threshold: float = 85,
    warning_threshold: float = 80,
    abv_tolerance: float = 0.3,
    volume_tolerance_pct: float = 1.0,
) -> list[FieldComparison]:
    """Compare all 7 mandatory label fields, returning one FieldComparison each."""
    results = [
        compare_text_field(
            "brand_name", extracted_fields.get("brand_name"), expected_fields.get("brand_name"), text_threshold
        ),
        compare_text_field(
            "class_type", extracted_fields.get("class_type"), expected_fields.get("class_type"), text_threshold
        ),
        compare_abv_field(
            extracted_fields.get("alcohol_content"), expected_fields.get("alcohol_content"), abv_tolerance
        ),
        compare_volume_field(
            extracted_fields.get("net_contents"), expected_fields.get("net_contents"), volume_tolerance_pct
        ),
        compare_text_field(
            "producer_info", extracted_fields.get("producer_info"), expected_fields.get("producer_info"), text_threshold
        ),
        compare_text_field(
            "country_of_origin",
            extracted_fields.get("country_of_origin"),
            expected_fields.get("country_of_origin"),
            text_threshold,
        ),
        compare_warning_field(
            extracted_fields.get("health_warning_text"),
            expected_fields.get("health_warning_text"),
            warning_threshold,
        ),
    ]
    return results
