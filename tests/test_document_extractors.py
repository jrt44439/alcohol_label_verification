from app.documents.field_extractors import LABELED_FIELD_PATTERNS, extract_all_fields_from_document, extract_labeled_field

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

# Simulates text extracted from a fillable COLA application PDF, where each
# field's label sits on its own line and the filled-in answer is on the
# line(s) below -- not "Label: value" on one line.
FORM_STYLE_COLA_TEXT = """\
7. BRAND NAME

Riverbend Reserve

8. CLASS AND TYPE OF PRODUCT

Chardonnay

9. NAME AND ADDRESS OF PRODUCER, BOTTLER, OR IMPORTER
(Include Plant Registry/Basic Permit Number)

Riverbend Winery
456 Vineyard Lane
Napa, CA 94558

10. COUNTRY OF ORIGIN

United States

INSTRUCTIONS: If the product is bottled by someone other than the producer,
provide the name of the bottler and the producer in item 9 above.
"""

BOILERPLATE_WITHOUT_PRODUCER_FIELD = """\
This form must be completed in full. If bottled by someone other than the
producer, provide the name of the bottler as well.
"""

FORM_WITH_TRAILING_NOISE = """\
CLASS AND TYPE OF PRODUCT: Cabernet Sauvignon (Front Label)

NAME AND ADDRESS OF PRODUCER: Golden Valley Cellars, 789 Hillside Ave, Sonoma, CA 95476 Rev. 2024-01
"""

FORM_WITH_INLINE_PARENTHETICAL_HEADING = """\
8. NAME AND ADDRESS OF PRODUCER, BOTTLER, OR IMPORTER (Include Plant Registry/Basic Permit Number): Riverbend Winery, 456 Vineyard Lane, Napa, CA 94558
"""

FORM_WITH_BARE_NAME_AND_ADDRESS_HEADING = """\
NAME AND ADDRESS

Golden Valley Cellars
789 Hillside Ave
Sonoma, CA 95476
"""

FORM_WITH_UNRECOGNIZED_NEXT_FIELD = """\
NAME AND ADDRESS OF PRODUCER

Golden Valley Cellars
789 Hillside Ave
Sonoma, CA 95476

Plant Registry or Basic Permit Number Assigned By The Bureau
TTB-12345
"""

FORM_WITH_TWO_LINE_CLASS_TYPE = """\
CLASS AND TYPE OF PRODUCT

Kentucky Straight
Bourbon Whiskey

9. NAME AND ADDRESS OF PRODUCER

Old Ridge Distillery, Frankfort, KY
"""

FORM_WITH_CHECKBOX_TYPE_OF_PRODUCT = """\
7. TYPE OF PRODUCT (Check one)

[ ] WINE   [X] DISTILLED SPIRITS   [ ] MALT BEVERAGE

8. BRAND NAME

Old Ridge
"""

FORM_WITH_BRAND_NAME_TRAILING_FRONT_NOISE = """\
BRAND NAME: Old Ridge (Front Label)
"""

FORM_WITH_APPLICANT_NAME_AND_ADDRESS = """\
8. NAME AND ADDRESS OF APPLICANT

Old Ridge Distillery
123 Barrel Rd
Frankfort, KY 40601

8A. MAILING ADDRESS (Only if different from Item 8)

PO Box 99
Frankfort, KY 40602
"""

FORM_WITH_APPLICANT_HEADING_TRAILING_WORDS = """\
8. NAME AND ADDRESS OF APPLICANT AS SHOWN ON PERMIT OR BREWER'S NOTICE

Old Ridge Distillery
123 Barrel Rd
Frankfort, Kentucky 40601 Rev. 2024-01
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
    # Bounded to the keyword + a following base-category word, not the whole
    # rambling sentence it appears in.
    assert result["class_type"] == "bourbon whiskey"
    assert result["alcohol_content"] == "45% ALC/VOL (90 PROOF)"
    assert result["net_contents"] == "750 mL"
    assert "Old Ridge Distillery" in result["producer_info"]


def test_extract_all_fields_from_form_style_document_with_label_on_own_line():
    result = extract_all_fields_from_document(FORM_STYLE_COLA_TEXT)
    # Multi-word brand name captured from the line below the label.
    assert result["brand_name"] == "Riverbend Reserve"
    # Wine varietal, not a generic category.
    assert result["class_type"] == "Chardonnay"
    # Multi-line address, with the parenthetical instruction skipped and the
    # producer heading/instructions text below it excluded.
    assert result["producer_info"] == "Riverbend Winery 456 Vineyard Lane Napa, CA 94558"
    assert "INSTRUCTIONS" not in result["producer_info"]
    assert result["country_of_origin"] == "United States"


def test_extract_labeled_field_producer_ignores_boilerplate_sentence():
    # "producer"/"bottler" mentioned in an instructional sentence, with no
    # real "Name and Address of..." field present, should not be picked up.
    assert (
        extract_labeled_field(BOILERPLATE_WITHOUT_PRODUCER_FIELD, LABELED_FIELD_PATTERNS["producer_info"], multiline=True)
        is None
    )


def test_extract_all_fields_producer_info_handles_inline_parenthetical_before_colon():
    # A real TTB-style heading with its instructional aside on the SAME
    # line as the label, before the colon: "...Importer (Include Plant
    # Registry/Basic Permit Number): <value>".
    result = extract_all_fields_from_document(FORM_WITH_INLINE_PARENTHETICAL_HEADING)
    assert result["producer_info"] == "Riverbend Winery, 456 Vineyard Lane, Napa, CA 94558"
    assert "Name and Address" not in result["producer_info"]
    assert "Include Plant Registry" not in result["producer_info"]


def test_extract_all_fields_producer_info_from_bare_name_and_address_heading():
    # Some forms head this field just "Name and Address", without "...of
    # Producer/Bottler/Importer" attached.
    result = extract_all_fields_from_document(FORM_WITH_BARE_NAME_AND_ADDRESS_HEADING)
    assert result["producer_info"] == "Golden Valley Cellars 789 Hillside Ave Sonoma, CA 95476"
    assert "Name and Address" not in result["producer_info"]


def test_extract_all_fields_strips_class_type_trailing_front_back_noise():
    result = extract_all_fields_from_document(FORM_WITH_TRAILING_NOISE)
    assert result["class_type"] == "Cabernet Sauvignon"


def test_extract_all_fields_producer_info_ends_at_address_not_trailing_noise():
    result = extract_all_fields_from_document(FORM_WITH_TRAILING_NOISE)
    assert result["producer_info"] == "Golden Valley Cellars, 789 Hillside Ave, Sonoma, CA 95476"


def test_extract_all_fields_producer_info_stops_before_unrecognized_next_field():
    # "Plant Registry or Basic Permit Number..." isn't one of our known
    # field-label patterns, so it wouldn't be caught as a heading -- the
    # zip-code-ending signal must stop capture before it regardless.
    result = extract_all_fields_from_document(FORM_WITH_UNRECOGNIZED_NEXT_FIELD)
    assert result["producer_info"] == "Golden Valley Cellars 789 Hillside Ave Sonoma, CA 95476"
    assert "Plant Registry" not in result["producer_info"]


def test_extract_all_fields_class_type_merges_two_content_lines():
    result = extract_all_fields_from_document(FORM_WITH_TWO_LINE_CLASS_TYPE)
    assert result["class_type"] == "Kentucky Straight Bourbon Whiskey"


def test_extract_all_fields_class_type_from_checkbox_type_of_product():
    result = extract_all_fields_from_document(FORM_WITH_CHECKBOX_TYPE_OF_PRODUCT)
    assert result["class_type"] == "Distilled Spirits"
    assert result["brand_name"] == "Old Ridge"


def test_extract_all_fields_brand_name_strips_trailing_front_back_noise():
    result = extract_all_fields_from_document(FORM_WITH_BRAND_NAME_TRAILING_FRONT_NOISE)
    assert result["brand_name"] == "Old Ridge"


def test_extract_all_fields_producer_info_from_name_and_address_of_applicant():
    result = extract_all_fields_from_document(FORM_WITH_APPLICANT_NAME_AND_ADDRESS)
    assert result["producer_info"] == "Old Ridge Distillery 123 Barrel Rd Frankfort, KY 40601"
    assert "MAILING ADDRESS" not in result["producer_info"]
    assert "PO Box" not in result["producer_info"]


def test_extract_all_fields_producer_info_heading_with_trailing_words():
    # The heading itself has more caps words after "APPLICANT" (not in
    # parentheses) -- must not be mistaken for the pattern matching mid-
    # sentence, and the trailing "Rev. 2024-01" noise after the full state
    # name + zip must still be trimmed off.
    result = extract_all_fields_from_document(FORM_WITH_APPLICANT_HEADING_TRAILING_WORDS)
    assert result["producer_info"] == "Old Ridge Distillery 123 Barrel Rd Frankfort, Kentucky 40601"
    assert "Rev" not in result["producer_info"]
