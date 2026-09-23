from app.documents.field_extractors import extract_all_fields_from_document, extract_labeled_field

LABELED_SPEC_SHEET = """\
Brand Name: Old Ridge
Class and Type: Kentucky Straight Bourbon Whiskey
Alcohol Content: 45% ALC/VOL
Net Contents: 750 mL
Name and Address of Producer: Old Ridge Distillery, Frankfort, KY
Country of Origin: United States
"""

UNLABELED_FREEFORM_TEXT = """\
This bourbon whiskey is bottled at 45% ALC/VOL (90 PROOF) in 750 mL bottles.
Produced by Old Ridge Distillery, Frankfort, KY.
"""


def test_extract_labeled_field_finds_value():
    assert extract_labeled_field(LABELED_SPEC_SHEET, ["BRAND\\s*NAME"]) == "Old Ridge"


def test_extract_labeled_field_absent_returns_none():
    assert extract_labeled_field(LABELED_SPEC_SHEET, ["IMPORTER"]) is None


def test_extract_all_fields_from_labeled_document():
    result = extract_all_fields_from_document(LABELED_SPEC_SHEET)
    assert result["brand_name"] == "Old Ridge"
    assert result["class_type"] == "Kentucky Straight Bourbon Whiskey"
    assert result["alcohol_content"] == "45% ALC/VOL"
    assert result["net_contents"] == "750 mL"
    assert "Old Ridge Distillery" in result["producer_info"]
    assert result["country_of_origin"] == "United States"


def test_extract_all_fields_falls_back_to_freeform_heuristics():
    result = extract_all_fields_from_document(UNLABELED_FREEFORM_TEXT)
    # No explicit "Brand Name:" label in freeform text, so brand_name stays unset.
    assert result["brand_name"] is None
    assert result["class_type"] == "This bourbon whiskey is bottled at 45% ALC/VOL (90 PROOF) in 750 mL bottles."
    assert result["alcohol_content"] == "45% ALC/VOL (90 PROOF)"
    assert result["net_contents"] == "750 mL"
    assert "Old Ridge Distillery" in result["producer_info"]
