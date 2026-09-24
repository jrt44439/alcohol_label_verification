from app.comparison.compare import (
    MatchStatus,
    aggregate_field,
    compare_abv_field,
    compare_product,
    compare_text_field,
    compare_volume_field,
    compare_warning_field,
    find_best_match,
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


def test_compare_text_field_class_type_broad_category_match_when_allowed():
    # A COLA application checkbox only records the broad category; the label
    # itself has the specific designation. Broad matching is opt-in.
    result = compare_text_field(
        "class_type", "Kentucky Straight Bourbon Whiskey", "Distilled Spirits", TEXT_THRESHOLD,
        allow_broad_class_type=True,
    )
    assert result.status == MatchStatus.MATCH

    result = compare_text_field(
        "class_type", "Chardonnay", "Wine", TEXT_THRESHOLD, allow_broad_class_type=True
    )
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_class_type_broad_category_not_applied_by_default():
    # Product-library matching must not treat "Vodka" and "Bourbon Whiskey"
    # as the same product just because they're both distilled spirits.
    result = compare_text_field("class_type", "Vodka", "Bourbon Whiskey", TEXT_THRESHOLD)
    assert result.status == MatchStatus.MISMATCH


def test_compare_text_field_class_type_broad_category_mismatch_across_categories():
    result = compare_text_field(
        "class_type", "Chardonnay", "Distilled Spirits", TEXT_THRESHOLD, allow_broad_class_type=True
    )
    assert result.status == MatchStatus.MISMATCH


def test_compare_text_field_producer_broad_match_missing_street_address():
    # The label's small fine print omitted the street address entirely,
    # but name, city, and state all agree.
    extracted = "Old Ridge Distillery, Frankfort, KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_full_vs_abbreviated_state():
    extracted = "Old Ridge Distillery Frankfort KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, Kentucky 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_tolerates_different_city_if_name_and_state_agree():
    # Even broader: this no longer requires the city to match too -- a
    # handful of shared keywords (here, the full producer name plus the
    # agreeing state) is enough, even though the city was misread/differs.
    extracted = "Old Ridge Distillery, Louisville, KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_requires_matching_state():
    # Name keywords alone ("old ridge distillery") aren't enough without an
    # agreeing state -- a completely different state is a strong enough
    # signal that this is actually a different location/producer.
    extracted = "Old Ridge Distillery, Louisville, KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Bend, OR 97701"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MISMATCH


def test_compare_text_field_producer_broad_match_requires_similar_name():
    extracted = "Blue Valley Spirits, Frankfort, KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MISMATCH


def test_compare_text_field_producer_broad_match_tolerates_misread_city_keyword():
    # "Frankfoit" (a plausible OCR misread of "Frankfort") doesn't show up
    # as a shared keyword at all -- but the name words plus the agreeing
    # state are still enough shared keywords on their own.
    extracted = "Old Ridge Distillery, Frankfoit, KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_tolerates_reordered_name_words():
    extracted = "Distillery Old Ridge, Frankfort, KY"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_just_a_few_shared_keywords_is_enough():
    # Short values: only 2 significant keywords ("acme", "nv") on the
    # shorter side, both shared -- that's already "a few keywords".
    extracted = "Acme Distillery, Reno, NV"
    expected = "Acme, NV"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_ignores_suffix_and_street_noise_words():
    extracted = "Old Ridge Distillery LLC, 456 Vineyard Lane, Frankfort, KY"
    expected = "Old Ridge Distillery Inc, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
    assert result.status == MatchStatus.MATCH


def test_compare_text_field_producer_broad_match_skipped_without_state():
    extracted = "Old Ridge Distillery"
    expected = "Old Ridge Distillery, 123 Barrel Rd, Frankfort, KY 40601"
    result = compare_text_field("producer_info", extracted, expected, TEXT_THRESHOLD)
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


def test_compare_abv_field_blank_label_is_not_found_even_if_reference_also_blank():
    # ABV is always mandatory on the label -- a reference source (e.g. a COLA
    # application) that also omitted it doesn't excuse the label from having it.
    result = compare_abv_field(None, None, ABV_TOLERANCE)
    assert result.status == MatchStatus.NOT_FOUND


def test_compare_abv_field_blank_label_is_not_found_when_reference_present():
    result = compare_abv_field(None, "45% ALC/VOL", ABV_TOLERANCE)
    assert result.status == MatchStatus.NOT_FOUND


def test_compare_abv_field_present_label_matches_blank_reference():
    # The reference source omitting it is fine as long as the label has it.
    result = compare_abv_field("45% ALC/VOL", None, ABV_TOLERANCE)
    assert result.status == MatchStatus.MATCH


def test_compare_volume_field_blank_label_is_not_found_even_if_reference_also_blank():
    result = compare_volume_field(None, None, VOLUME_TOLERANCE_PCT)
    assert result.status == MatchStatus.NOT_FOUND


def test_compare_volume_field_blank_label_is_not_found_when_reference_present():
    result = compare_volume_field(None, "750 mL", VOLUME_TOLERANCE_PCT)
    assert result.status == MatchStatus.NOT_FOUND


def test_compare_volume_field_present_label_matches_blank_reference():
    result = compare_volume_field("750 mL", None, VOLUME_TOLERANCE_PCT)
    assert result.status == MatchStatus.MATCH


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


REFERENCE_FIELDS = {
    "brand_name": "Old Ridge",
    "class_type": "Bourbon Whiskey",
    "alcohol_content": "45% ALC/VOL",
    "net_contents": "750 mL",
    "producer_info": "Old Ridge Distillery, Frankfort, KY",
    "country_of_origin": None,
}


def test_find_best_match_prefers_exact_over_partial():
    exact_candidate = {"id": "exact", **REFERENCE_FIELDS}
    partial_candidate = {"id": "partial", **{**REFERENCE_FIELDS, "class_type": "Rye Whiskey", "net_contents": "375 mL"}}

    best_id, matched_count = find_best_match(REFERENCE_FIELDS, [partial_candidate, exact_candidate])
    assert best_id == "exact"
    assert matched_count == 6


def test_find_best_match_ties_broken_by_score():
    # Both candidates mismatch on brand_name, but "close" is a near-miss
    # (higher fuzzy score) while "far" is a completely different string.
    close_candidate = {"id": "close", **{**REFERENCE_FIELDS, "brand_name": "Old Ridge Brewing Co"}}
    far_candidate = {"id": "far", **{**REFERENCE_FIELDS, "brand_name": "Totally Different"}}

    best_id, matched_count = find_best_match(REFERENCE_FIELDS, [far_candidate, close_candidate])
    assert best_id == "close"
    assert matched_count == 5


def test_find_best_match_empty_candidates():
    assert find_best_match(REFERENCE_FIELDS, []) == (None, 0)


def test_find_best_match_no_candidate_matches_anything():
    unrelated = {
        "id": "unrelated",
        "brand_name": "Nothing Alike",
        "class_type": "Vodka",
        "alcohol_content": "40% ALC/VOL",
        "net_contents": "1 L",
        "producer_info": "Somewhere Else",
        "country_of_origin": "Elsewhere",
    }
    assert find_best_match(REFERENCE_FIELDS, [unrelated]) == (None, 0)


def _make_item(index, extracted, expected):
    comparisons = compare_product(extracted, expected, TEXT_THRESHOLD, WARNING_THRESHOLD, ABV_TOLERANCE, VOLUME_TOLERANCE_PCT)
    return {
        "index": index,
        "extracted": extracted,
        "expected": expected,
        "comparisons_by_field": {c.field_key: c for c in comparisons},
    }


AGGREGATE_EXPECTED = {
    "brand_name": "Old Ridge",
    "class_type": "Bourbon",
    "alcohol_content": "45% ALC/VOL",
    "net_contents": "750 mL",
    "producer_info": "Old Ridge Distillery",
    "country_of_origin": None,
    "health_warning_text": "GOVERNMENT WARNING: ...",
}


def _aggregate(field_key, items):
    return aggregate_field(field_key, items, TEXT_THRESHOLD, WARNING_THRESHOLD, ABV_TOLERANCE, VOLUME_TOLERANCE_PCT)


def test_aggregate_field_match_wins_over_mismatch_on_another_photo():
    item_a = _make_item(0, {**AGGREGATE_EXPECTED, "net_contents": "375 mL"}, AGGREGATE_EXPECTED)  # wrong reading
    item_b = _make_item(1, {**AGGREGATE_EXPECTED, "net_contents": "750 mL"}, AGGREGATE_EXPECTED)  # correct reading

    result = _aggregate("net_contents", [item_a, item_b])
    assert result["status"] == "match"
    assert result["source_index"] == 1


def test_aggregate_field_consistent_mismatch_across_photos():
    item_a = _make_item(0, {**AGGREGATE_EXPECTED, "net_contents": "375 mL"}, AGGREGATE_EXPECTED)
    item_b = _make_item(1, {**AGGREGATE_EXPECTED, "net_contents": "375 mL"}, AGGREGATE_EXPECTED)  # agrees, both wrong

    result = _aggregate("net_contents", [item_a, item_b])
    assert result["status"] == "mismatch"
    assert result["value"] == "375 mL"


def test_aggregate_field_disagreement_between_photos():
    item_a = _make_item(0, {**AGGREGATE_EXPECTED, "net_contents": "375 mL"}, AGGREGATE_EXPECTED)
    item_b = _make_item(1, {**AGGREGATE_EXPECTED, "net_contents": "700 mL"}, AGGREGATE_EXPECTED)  # conflicting

    result = _aggregate("net_contents", [item_a, item_b])
    assert result["status"] == "disagreement"
    assert {v["value"] for v in result["values"]} == {"375 mL", "700 mL"}


def test_aggregate_field_not_found_when_blank_everywhere():
    item_a = _make_item(0, {**AGGREGATE_EXPECTED, "net_contents": None}, AGGREGATE_EXPECTED)
    item_b = _make_item(1, {**AGGREGATE_EXPECTED, "net_contents": None}, AGGREGATE_EXPECTED)

    result = _aggregate("net_contents", [item_a, item_b])
    assert result["status"] == "not_found"
