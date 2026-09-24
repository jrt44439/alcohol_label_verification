"""Per-field comparison logic between OCR-extracted label values and the
user's expected/reference values."""
import re
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz

from config import CLASS_TYPE_BROAD_CATEGORY
from app.comparison.normalize import normalize_abv, normalize_text, normalize_volume
from app.ocr import field_extractors as ocr_field_extractors

# Longest keyword first, so e.g. "kentucky straight bourbon" is matched
# before the bare "bourbon" it contains.
_BROAD_CATEGORY_KEYWORDS_BY_LENGTH = sorted(CLASS_TYPE_BROAD_CATEGORY, key=len, reverse=True)


def _class_type_broad_category(value: str | None) -> str | None:
    """Map a class/type value (a specific designation like "Bourbon Whiskey"
    or "Chardonnay", or already a broad category like "Wine") to its broad
    TTB product category, or None if no known keyword is found."""
    if not value:
        return None
    lowered = normalize_text(value)
    for keyword in _BROAD_CATEGORY_KEYWORDS_BY_LENGTH:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return CLASS_TYPE_BROAD_CATEGORY[keyword]
    return None


# Filler words that don't help identify a producer -- dropped before
# counting shared keywords, so e.g. a differing suite number or "LLC" vs
# "Inc" doesn't cost a match.
_PRODUCER_NOISE_WORDS = {
    "street", "st", "avenue", "ave", "road", "rd", "lane", "ln", "drive",
    "dr", "boulevard", "blvd", "suite", "ste", "unit", "floor", "fl",
    "way", "highway", "hwy", "llc", "inc", "co", "company", "corp", "ltd",
}


def _producer_keywords(value: str | None) -> set[str]:
    """Significant, comparable keyword tokens from a producer/address
    value -- lowercased and punctuation-stripped, with any full state name
    normalized to its 2-letter abbreviation first (so "Kentucky" and "KY"
    count as the same keyword), common street/corporate filler words and
    pure-digit tokens (street numbers, zip codes) dropped."""
    if not value:
        return set()
    normalized = ocr_field_extractors.normalize_states_in_text(value)
    words = normalize_text(normalized).split()
    return {w for w in words if w not in _PRODUCER_NOISE_WORDS and not w.isdigit() and len(w) > 1}


def _producer_state(value: str | None) -> str | None:
    if not value:
        return None
    match = ocr_field_extractors.find_state_match(value)
    return ocr_field_extractors.normalize_state(match.group(0)) if match else None


def _producer_broad_match(a: str | None, b: str | None) -> bool:
    """Whether two producer/address values broadly match. A recognized
    state has to be found on both sides and agree -- abbreviation and full
    name normalized to the same form (e.g. "Kentucky" == "KY") -- that's
    the one non-negotiable signal. Beyond that, this just looks for a
    handful of shared keywords (name words, city, ...) between the two
    values rather than requiring them to be split into precise name/city
    components -- tolerant of a missing street address, reordered words,
    minor OCR noise, punctuation, or even a differently-read city, as long
    as enough of the rest still lines up."""
    state_a, state_b = _producer_state(a), _producer_state(b)
    if not state_a or not state_b or state_a != state_b:
        return False

    keywords_a, keywords_b = _producer_keywords(a), _producer_keywords(b)
    smaller = min(len(keywords_a), len(keywords_b))
    if smaller < 2:
        return False
    required = min(3, smaller)
    return len(keywords_a & keywords_b) >= required


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
    field_key: str,
    extracted: str | None,
    expected: str | None,
    threshold: float,
    allow_broad_class_type: bool = False,
) -> FieldComparison:
    display_name = FIELD_DISPLAY_NAMES[field_key]

    if _is_blank(extracted):
        status = MatchStatus.MATCH if _is_blank(expected) else MatchStatus.NOT_FOUND
        return FieldComparison(field_key, display_name, extracted, expected, status, None)

    if _is_blank(expected):
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.MATCH, None)

    score = fuzz.token_sort_ratio(normalize_text(extracted), normalize_text(expected))
    status = MatchStatus.MATCH if score >= threshold else MatchStatus.MISMATCH

    if status == MatchStatus.MISMATCH and field_key == "class_type" and allow_broad_class_type:
        # A COLA application often only records the broad product category
        # (Wine / Distilled Spirits / Malt Beverage) rather than the
        # specific designation printed on the label -- e.g. "Bourbon
        # Whiskey" vs. "Distilled Spirits", or "Chardonnay" vs. "Wine".
        # Treat those as matching rather than flagging a mismatch.
        extracted_category = _class_type_broad_category(extracted)
        expected_category = _class_type_broad_category(expected)
        if extracted_category and extracted_category == expected_category:
            status = MatchStatus.MATCH

    if status == MatchStatus.MISMATCH and field_key == "producer_info":
        # One side (often the photographed label, especially small fine
        # print) may be missing words the other has -- a street address, a
        # suffix like "LLC", punctuation. If both still agree on producer
        # name, city, and state, that's a broad enough match.
        if _producer_broad_match(extracted, expected):
            status = MatchStatus.MATCH

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
        # Alcohol content is always mandatory on the label itself -- unlike
        # e.g. country of origin, a blank reference value never excuses it.
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.NOT_FOUND, None)

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
        # Net contents is always mandatory on the label itself -- unlike
        # e.g. country of origin, a blank reference value never excuses it.
        return FieldComparison(field_key, display_name, extracted, expected, MatchStatus.NOT_FOUND, None)

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


def compare_reference_fields(
    extracted_fields: dict[str, str | None],
    expected_fields: dict[str, str | None],
    text_threshold: float = 85,
    abv_tolerance: float = 0.3,
    volume_tolerance_pct: float = 1.0,
    allow_broad_class_type: bool = False,
) -> list[FieldComparison]:
    """Compare the 6 product-identifying fields (brand, class/type, ABV, net
    contents, producer, country of origin) -- everything except the
    Government Warning, whose expected value is a fixed constant rather than
    product-specific data. Used both for full display and for scoring how
    well a photo matches a candidate product (see find_best_match).

    ``allow_broad_class_type`` should only be set when ``expected_fields``
    comes from a COLA application (which sometimes only records the broad
    product category, not a specific designation) -- leaving it off for
    product-library matching, where "Vodka" and "Bourbon Whiskey" must not
    be treated as the same product."""
    return [
        compare_text_field(
            "brand_name", extracted_fields.get("brand_name"), expected_fields.get("brand_name"), text_threshold
        ),
        compare_text_field(
            "class_type",
            extracted_fields.get("class_type"),
            expected_fields.get("class_type"),
            text_threshold,
            allow_broad_class_type=allow_broad_class_type,
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
    ]


def compare_product(
    extracted_fields: dict[str, str | None],
    expected_fields: dict[str, str | None],
    text_threshold: float = 85,
    warning_threshold: float = 80,
    abv_tolerance: float = 0.3,
    volume_tolerance_pct: float = 1.0,
    allow_broad_class_type: bool = False,
) -> list[FieldComparison]:
    """Compare all 7 mandatory label fields, returning one FieldComparison each.
    See compare_reference_fields for ``allow_broad_class_type``."""
    results = compare_reference_fields(
        extracted_fields, expected_fields, text_threshold, abv_tolerance, volume_tolerance_pct, allow_broad_class_type
    )
    results.append(
        compare_warning_field(
            extracted_fields.get("health_warning_text"),
            expected_fields.get("health_warning_text"),
            warning_threshold,
        )
    )
    return results


def find_best_match(
    extracted_fields: dict[str, str | None],
    candidates: list[dict],
    text_threshold: float = 85,
    abv_tolerance: float = 0.3,
    volume_tolerance_pct: float = 1.0,
) -> tuple[object, int]:
    """Scan candidate products for the best match to extracted label fields.

    ``candidates`` is a list of dicts, each with an ``"id"`` key plus the 6
    product-identifying fields. Returns (best_candidate_id, matched_count) --
    matched_count is how many of the 6 fields came back MATCH for the winner,
    tie-broken by summed fuzzy score then candidate order. Returns
    (None, 0) if candidates is empty or nothing matched at all.
    """
    best_id = None
    best_matched = -1
    best_score = -1.0

    for candidate in candidates:
        comparisons = compare_reference_fields(
            extracted_fields, candidate, text_threshold, abv_tolerance, volume_tolerance_pct
        )
        matched = sum(1 for c in comparisons if c.status == MatchStatus.MATCH)
        score_sum = sum(c.score or 0 for c in comparisons)

        if matched > best_matched or (matched == best_matched and score_sum > best_score):
            best_id = candidate["id"]
            best_matched = matched
            best_score = score_sum

    if best_id is None or best_matched <= 0:
        return None, 0
    return best_id, best_matched


def _values_agree(
    field_key: str,
    a: str,
    b: str,
    text_threshold: float,
    warning_threshold: float,
    abv_tolerance: float,
    volume_tolerance_pct: float,
) -> bool:
    """Whether two non-blank extracted readings for the same field, taken
    from different photos, agree with each other -- a symmetric comparison,
    independent of whether either one matches any expected/reference value."""
    if field_key == "alcohol_content":
        pct_a, _ = normalize_abv(a)
        pct_b, _ = normalize_abv(b)
        if pct_a is not None and pct_b is not None:
            return abs(pct_a - pct_b) <= abv_tolerance
    elif field_key == "net_contents":
        ml_a = normalize_volume(a)
        ml_b = normalize_volume(b)
        if ml_a is not None and ml_b is not None:
            pct_diff = abs(ml_a - ml_b) / ml_b * 100 if ml_b else 100.0
            return pct_diff <= volume_tolerance_pct

    threshold = warning_threshold if field_key == "health_warning_text" else text_threshold
    score_func = fuzz.partial_ratio if field_key == "health_warning_text" else fuzz.token_sort_ratio
    score = score_func(normalize_text(a), normalize_text(b))
    return score >= threshold


def aggregate_field(
    field_key: str,
    items: list[dict],
    text_threshold: float = 85,
    warning_threshold: float = 80,
    abv_tolerance: float = 0.3,
    volume_tolerance_pct: float = 1.0,
) -> dict:
    """Aggregate one field's comparison across every photo in a group (e.g.
    front + back photos of one product), answering "does this mandatory
    field appear correctly *somewhere* in this set of label photos" rather
    than judging each photo in isolation.

    ``items`` is a list of dicts, each with ``index``, ``extracted``,
    ``expected``, and ``comparisons_by_field`` (exactly what
    app/routes/verify.py already builds per photo).

    Returns a dict with a "status" of:
    - "match": found correctly (per compare_product) on at least one photo.
      A match on one photo isn't dragged down by a conflicting misread on
      another -- includes "value"/"source_index" of the matching photo.
    - "mismatch": found on one or more photos, none matched, but every photo
      that found something agrees with the others (consistently wrong, not
      conflicting) -- includes "value"/"source_index" of the first one.
    - "disagreement": two or more photos found different, conflicting
      readings and none matched -- includes "values", a list of
      {"value", "source_index"} for every non-blank reading.
    - "not_found": blank on every photo in the group.
    All statuses include "expected" for display.
    """
    expected_value = items[0]["expected"].get(field_key) if items else None

    matched = [it for it in items if it["comparisons_by_field"][field_key].status == MatchStatus.MATCH]
    if matched:
        winner = matched[0]
        return {
            "status": "match",
            "value": winner["extracted"].get(field_key),
            "source_index": winner["index"],
            "expected": winner["expected"].get(field_key),
        }

    non_blank = [it for it in items if not _is_blank(it["extracted"].get(field_key))]
    if not non_blank:
        return {"status": "not_found", "expected": expected_value}

    first_value = non_blank[0]["extracted"].get(field_key)
    all_agree = all(
        _values_agree(
            field_key,
            first_value,
            it["extracted"].get(field_key),
            text_threshold,
            warning_threshold,
            abv_tolerance,
            volume_tolerance_pct,
        )
        for it in non_blank[1:]
    )

    if not all_agree:
        return {
            "status": "disagreement",
            "values": [{"value": it["extracted"].get(field_key), "source_index": it["index"]} for it in non_blank],
            "expected": expected_value,
        }

    return {
        "status": "mismatch",
        "value": first_value,
        "source_index": non_blank[0]["index"],
        "expected": non_blank[0]["expected"].get(field_key),
    }
