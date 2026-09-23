from app.comparison.compare import (
    MatchStatus,
    compare_abv_field,
    compare_product,
    compare_text_field,
    compare_volume_field,
    compare_warning_field,
)

TEXT_THRESHOLD = 85
WARNING_THRESHOLD = 80
ABV_TOLERANCE = 0.3
VOLUME_TOLERANCE_PCT = 1.0


def test_compare_text_field_match():
    result = compare_text_field("brand_name", "Old Ridge", "old ridge", TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_mismatch():
    result = compare_text_field("brand_name", "Old Ridge", "New Summit", TEXT_THRESHOLD)
    assert result.status == MatchStatus.MISMATCH


def test_compare_text_field_not_found():
    result = compare_text_field("brand_name", None, "Old Ridge", TEXT_THRESHOLD)
    assert result.status == MatchStatus.NOT_FOUND


def test_compare_text_field_both_blank_matches():
    result = compare_text_field("country_of_origin", None, None, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_extracted_present_expected_blank_matches():
    # Nothing was entered to compare against, so we don't flag it as a problem.
    result = compare_text_field("country_of_origin", "France", None, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_abv_field_within_tolerance():
    result = compare_abv_field("45.1% ALC/VOL", "45% ALC/VOL", ABV_TOLERANCE)
    assert result.status == MatchStatus.MATCH


def test_compare_abv_field_outside_tolerance():
    result = compare_abv_field("40% ALC/VOL", "45% ALC/VOL", ABV_TOLERANCE)
    assert result.status == MatchStatus.MISMATCH


def test_compare_abv_field_percent_matches_equivalent_proof():
    result = compare_abv_field("90 PROOF", "45% ALC/VOL", ABV_TOLERANCE)
    assert result.status == MatchStatus.MATCH


def test_compare_volume_field_match_after_unit_conversion():
    result = compare_volume_field("750mL", "0.75 L", VOLUME_TOLERANCE_PCT)
    assert result.status == MatchStatus.MATCH


def test_compare_volume_field_mismatch():
    result = compare_volume_field("375 mL", "750 mL", VOLUME_TOLERANCE_PCT)
    assert result.status == MatchStatus.MISMATCH


def test_compare_warning_field_tolerates_ocr_noise():
    canonical = (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
        "drink alcoholic beverages during pregnancy because of the risk of birth "
        "defects. (2) Consumption of alcoholic beverages impairs your ability to "
        "drive a car or operate machinery, and may cause health problems."
    )
    noisy = canonical.replace(",", "").replace(".", "").lower()
    result = compare_warning_field(noisy, canonical, WARNING_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_warning_field_missing_is_not_found():
    result = compare_warning_field(None, "GOVERNMENT WARNING: ...", WARNING_THRESHOLD)
    assert result.status == MatchStatus.NOT_FOUND


def test_compare_product_returns_seven_fields():
    extracted = {
        "brand_name": "Old Ridge",
        "class_type": "Bourbon",
        "alcohol_content": "45% ALC/VOL",
        "net_contents": "750 mL",
        "producer_info": "Old Ridge Distillery, Frankfort, KY",
        "country_of_origin": None,
        "health_warning_text": None,
    }
    expected = dict(extracted)
    expected["health_warning_text"] = "GOVERNMENT WARNING: ..."

    results = compare_product(extracted, expected)
    assert len(results) == 7
    statuses = {r.field_key: r.status for r in results}
    assert statuses["brand_name"] == MatchStatus.MATCH
    assert statuses["health_warning_text"] == MatchStatus.NOT_FOUND
    assert statuses["country_of_origin"] == MatchStatus.MATCH
