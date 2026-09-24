from app.ocr import field_extractors
from app.ocr.engine import OcrResult, WordBox
from fixtures.ocr_samples import (
    ABSENT_FIELDS_LABEL,
    CLEAN_BOURBON_LABEL,
    IMPORTED_WINE_LABEL,
    MULTILINE_ADDRESS_LABEL,
    NOISY_BOURBON_LABEL,
    PROOF_ONLY_LABEL,
)


def test_extract_abv_clean():
    assert field_extractors.extract_abv(CLEAN_BOURBON_LABEL) == "45% ALC/VOL (90 PROOF)"


def test_extract_abv_noisy_percent_only():
    assert field_extractors.extract_abv(NOISY_BOURBON_LABEL) == "45% ALC/VOL"


def test_extract_abv_proof_only():
    assert field_extractors.extract_abv(PROOF_ONLY_LABEL) == "80 PROOF"


def test_extract_abv_absent():
    assert field_extractors.extract_abv(ABSENT_FIELDS_LABEL) is None


def test_extract_net_contents_clean():
    assert field_extractors.extract_net_contents(CLEAN_BOURBON_LABEL) == "750 mL"


def test_extract_net_contents_no_space():
    assert field_extractors.extract_net_contents(NOISY_BOURBON_LABEL) == "750 ML"


def test_extract_net_contents_liters():
    assert field_extractors.extract_net_contents(PROOF_ONLY_LABEL) == "1.75 L"


def test_extract_net_contents_absent():
    assert field_extractors.extract_net_contents(ABSENT_FIELDS_LABEL) is None


def test_extract_producer_info_clean():
    result = field_extractors.extract_producer_info(CLEAN_BOURBON_LABEL)
    assert result is not None
    assert "Old Ridge Distillery" in result


def test_extract_producer_info_does_not_swallow_country_line():
    result = field_extractors.extract_producer_info(IMPORTED_WINE_LABEL)
    assert result is not None
    assert "Grand Cru Imports" in result
    assert "France" not in result


def test_extract_producer_info_absent():
    assert field_extractors.extract_producer_info(ABSENT_FIELDS_LABEL) is None


def test_extract_producer_info_tolerates_stray_blank_line_in_address():
    result = field_extractors.extract_producer_info(MULTILINE_ADDRESS_LABEL)
    assert result is not None
    assert "Summit Peak Distillers" in result
    assert "123 Mountain Road" in result
    assert "Denver, CO 80202" in result
    assert "GOVERNMENT WARNING" not in result


def test_extract_country_of_origin_present():
    assert field_extractors.extract_country_of_origin(IMPORTED_WINE_LABEL) == "France"


def test_extract_country_of_origin_domestic_is_none():
    assert field_extractors.extract_country_of_origin(CLEAN_BOURBON_LABEL) is None


def test_extract_class_type_bourbon():
    assert field_extractors.extract_class_type(CLEAN_BOURBON_LABEL) == "Kentucky Straight Bourbon Whiskey"


def test_extract_class_type_wine():
    assert field_extractors.extract_class_type(IMPORTED_WINE_LABEL) == "Red Wine"


def test_extract_class_type_absent():
    assert field_extractors.extract_class_type(ABSENT_FIELDS_LABEL) is None


def test_extract_class_type_does_not_grab_unrelated_trailing_words():
    text = "Kentucky Straight Bourbon Whiskey Distilled and Bottled by XYZ Distillery"
    assert field_extractors.extract_class_type(text) == "Kentucky Straight Bourbon Whiskey"


def test_extract_class_type_strips_front_back_noise():
    assert field_extractors.extract_class_type("Chardonnay (Front Label)") == "Chardonnay"


def test_extract_class_type_from_checkbox_picks_checked_box():
    text = "[ ] WINE   [X] DISTILLED SPIRITS   [ ] MALT BEVERAGE"
    assert field_extractors.extract_class_type_from_checkbox(text) == "Distilled Spirits"


def test_extract_class_type_from_checkbox_wine_checked():
    text = "(X) Wine  ( ) Distilled Spirits  ( ) Malt Beverage"
    assert field_extractors.extract_class_type_from_checkbox(text) == "Wine"


def test_extract_class_type_from_checkbox_no_mark_returns_none():
    text = "[ ] WINE   [ ] DISTILLED SPIRITS   [ ] MALT BEVERAGE"
    assert field_extractors.extract_class_type_from_checkbox(text) is None


def test_extract_class_type_merges_keyword_split_across_two_lines():
    # The class/type designation is printed across two lines on the label,
    # so it lands on two separate OCR'd text lines too.
    text = "Kentucky Straight\nBourbon Whiskey"
    assert field_extractors.extract_class_type(text) == "Kentucky Straight Bourbon Whiskey"


def test_extract_class_type_ignores_non_adjacent_keyword_words():
    # "red" and "wine" are far apart -- the listed keyword "red wine" must
    # not match across unrelated words sitting in between.
    text = "The red car is parked near the wine cellar."
    result = field_extractors.extract_class_type(text)
    assert result is not None
    assert "red wine" not in result.lower()


def test_strip_class_type_label_prefix():
    assert field_extractors.strip_class_type_label_prefix("Class/Type: Chardonnay") == "Chardonnay"
    assert field_extractors.strip_class_type_label_prefix("CLASS AND TYPE OF PRODUCT: Vodka") == "Vodka"


def test_trim_to_address_end_stops_at_zip():
    value = "Riverbend Winery 456 Vineyard Lane Napa CA 94558 Additional Instructions Here"
    assert field_extractors.trim_to_address_end(value) == "Riverbend Winery 456 Vineyard Lane Napa CA 94558"


def test_trim_to_address_end_leaves_unchanged_without_zip_state_or_country():
    value = "Some Producer Name With No Recognizable Address Ending"
    assert field_extractors.trim_to_address_end(value) == value


def test_looks_like_address_end_true_for_zip_state_or_country():
    assert field_extractors.looks_like_address_end("Napa, CA 94558") is True
    assert field_extractors.looks_like_address_end("Paris, France") is True
    assert field_extractors.looks_like_address_end("Just some text") is False


def test_looks_like_address_end_covers_additional_countries():
    # Beyond the original short list -- common import/export partners for
    # alcohol producers that weren't previously recognized.
    for country in ("Mexico", "Chile", "New Zealand", "South Korea", "Georgia"):
        assert field_extractors.looks_like_address_end(f"Some City, {country}") is True


def test_extract_producer_info_stops_when_whole_address_is_on_the_anchor_line():
    # The entire address, including its zip, is already on the "Produced
    # by" line -- nothing on the following unrelated line should be pulled
    # in, even though it contains a number that could look like a zip code.
    text = (
        "Produced by Example Distillery, 100 Main St, Louisville, KY 40202\n"
        "Reference Number: 12345 for Office CA\n"
    )
    result = field_extractors.extract_producer_info(text)
    assert result == "Produced by Example Distillery, 100 Main St, Louisville, KY 40202"


def test_extract_producer_info_stops_right_after_wrapped_address_ends():
    text = (
        "Produced by\n"
        "Example Distillery\n"
        "100 Main St\n"
        "Louisville, KY 40202\n"
        "Reference Number: 12345 for Office CA\n"
    )
    result = field_extractors.extract_producer_info(text)
    assert result == "Produced by Example Distillery 100 Main St Louisville, KY 40202"


def test_extract_producer_info_stops_at_address_end():
    text = (
        "Produced by Riverbend Winery, 456 Vineyard Lane, Napa, CA 94558\n"
        "Please retain this document for your records.\n"
    )
    result = field_extractors.extract_producer_info(text)
    assert result == "Produced by Riverbend Winery, 456 Vineyard Lane, Napa, CA 94558"


def test_extract_health_warning_present():
    result = field_extractors.extract_health_warning(CLEAN_BOURBON_LABEL)
    assert result is not None
    assert result.startswith("GOVERNMENT WARNING")
    assert "Surgeon General" in result


def test_extract_health_warning_case_insensitive():
    result = field_extractors.extract_health_warning(NOISY_BOURBON_LABEL)
    assert result is not None
    assert "surgeon general" in result.lower()


def test_extract_health_warning_absent():
    assert field_extractors.extract_health_warning(ABSENT_FIELDS_LABEL) is None


def _word(text, height, top, left=0, block_num=1, par_num=1, line_num=1):
    return WordBox(
        text=text, conf=90, left=left, top=top, width=50, height=height,
        block_num=block_num, par_num=par_num, line_num=line_num,
    )


def test_extract_brand_name_picks_tallest_non_excluded_line():
    words = [
        # Brand line: tall text near the top.
        _word("OLD", height=60, top=10, left=0, line_num=1),
        _word("RIDGE", height=60, top=10, left=60, line_num=1),
        # Class/type line: shorter text below the brand.
        _word("Bourbon", height=20, top=80, left=0, line_num=2),
        _word("Whiskey", height=20, top=80, left=60, line_num=2),
        # A line that should be excluded because it matches ABV pattern.
        _word("45%", height=25, top=120, left=0, line_num=3),
        _word("ALC/VOL", height=25, top=120, left=40, line_num=3),
    ]
    ocr_result = OcrResult(raw_text="OLD RIDGE Bourbon Whiskey 45% ALC/VOL", words=words)
    assert field_extractors.extract_brand_name(ocr_result) == "OLD RIDGE"


def test_extract_brand_name_no_words_returns_none():
    ocr_result = OcrResult(raw_text="", words=[])
    assert field_extractors.extract_brand_name(ocr_result) is None


def test_extract_brand_name_merges_stacked_two_line_logo():
    words = [
        # A brand name stacked across two lines (e.g. a logo), both tall.
        _word("MOUNTAIN", height=58, top=10, left=0, line_num=1),
        _word("PEAK", height=55, top=65, left=0, line_num=2),
        # Class/type line: noticeably shorter, should not be merged in.
        _word("Bourbon", height=20, top=130, left=0, line_num=3),
    ]
    ocr_result = OcrResult(raw_text="MOUNTAIN PEAK Bourbon", words=words)
    assert field_extractors.extract_brand_name(ocr_result) == "MOUNTAIN PEAK"


def test_extract_brand_name_does_not_merge_much_shorter_next_line():
    words = [
        _word("OLD", height=60, top=10, left=0, line_num=1),
        _word("RIDGE", height=60, top=10, left=60, line_num=1),
        _word("Bourbon", height=20, top=80, left=0, line_num=2),
        _word("Whiskey", height=20, top=80, left=60, line_num=2),
    ]
    ocr_result = OcrResult(raw_text="OLD RIDGE Bourbon Whiskey", words=words)
    assert field_extractors.extract_brand_name(ocr_result) == "OLD RIDGE"


def test_extract_producer_info_from_words_merges_multiline_address():
    words = [
        _word("Produced", height=20, top=100, left=0, line_num=1),
        _word("by", height=20, top=100, left=90, line_num=1),
        _word("Old", height=20, top=124, left=0, line_num=2),
        _word("Ridge", height=20, top=124, left=40, line_num=2),
        _word("Distillery", height=20, top=124, left=90, line_num=2),
        _word("Frankfort,", height=20, top=148, left=0, line_num=3),
        _word("KY", height=20, top=148, left=100, line_num=3),
        _word("40601", height=20, top=148, left=130, line_num=3),
    ]
    ocr_result = OcrResult(raw_text="", words=words)
    result = field_extractors.extract_producer_info_from_words(ocr_result)
    assert result == "Produced by Old Ridge Distillery Frankfort, KY 40601"


def test_extract_producer_info_from_words_excludes_smaller_font_fine_print():
    # No zip/state in this text at all, so only the font-size guard (via
    # cluster_lines) can keep the smaller-font fine print out.
    words = [
        _word("Produced", height=20, top=100, left=0, line_num=1),
        _word("by", height=20, top=100, left=90, line_num=1),
        _word("Old", height=20, top=124, left=0, line_num=2),
        _word("Ridge", height=20, top=124, left=40, line_num=2),
        _word("Distillery", height=20, top=124, left=90, line_num=2),
        _word("Enjoy", height=10, top=150, left=0, line_num=3),
        _word("responsibly.", height=10, top=150, left=45, line_num=3),
    ]
    ocr_result = OcrResult(raw_text="", words=words)
    result = field_extractors.extract_producer_info_from_words(ocr_result)
    assert result == "Produced by Old Ridge Distillery"
    assert "responsibly" not in result.lower()


def test_extract_producer_info_from_words_returns_none_without_anchor():
    words = [_word("Hello", height=20, top=0, left=0, line_num=1)]
    ocr_result = OcrResult(raw_text="Hello", words=words)
    assert field_extractors.extract_producer_info_from_words(ocr_result) is None


def test_extract_brand_name_merges_across_wider_gap_than_default_cluster_tolerance():
    # Gap here (130px, height 60) exceeds the general-purpose cluster_lines
    # default tolerance (max_gap_ratio 1.8 -> 108px) but is within the wider
    # tolerance extract_brand_name now uses (2.5 -> 150px) for a stacked
    # logo with extra breathing room between its lines.
    words = [
        _word("OLD RIDGE", height=60, top=10, left=0, line_num=1),
        _word("DISTILLERY", height=60, top=200, left=0, line_num=2),
    ]
    ocr_result = OcrResult(raw_text="OLD RIDGE DISTILLERY", words=words)
    assert field_extractors.extract_brand_name(ocr_result) == "OLD RIDGE DISTILLERY"


def test_extract_brand_name_merges_line_from_a_different_tesseract_block():
    # A brand name/logo split across separate Tesseract blocks (not just
    # separate lines within one block) should still merge, since the search
    # now scans the whole page's line order rather than one block only.
    words = [
        _word("OLD RIDGE", height=60, top=10, left=0, block_num=1, par_num=1, line_num=1),
        _word("DISTILLERY", height=60, top=65, left=0, block_num=2, par_num=1, line_num=1),
    ]
    ocr_result = OcrResult(raw_text="OLD RIDGE DISTILLERY", words=words)
    assert field_extractors.extract_brand_name(ocr_result) == "OLD RIDGE DISTILLERY"


def test_extract_brand_name_does_not_merge_same_height_line_far_below():
    # Same font size as the brand name, but separated by a large vertical
    # gap -- a visually unrelated block of text, not a stacked brand name.
    words = [
        _word("OLD RIDGE", height=60, top=10, left=0, line_num=1),
        _word("RESERVE", height=60, top=400, left=0, line_num=2),
    ]
    ocr_result = OcrResult(raw_text="OLD RIDGE RESERVE", words=words)
    assert field_extractors.extract_brand_name(ocr_result) == "OLD RIDGE"
