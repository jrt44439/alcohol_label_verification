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


def _word(text, height, top, left=0, block_num=1, line_num=1):
    return WordBox(text=text, conf=90, left=left, top=top, width=50, height=height, block_num=block_num, line_num=line_num)


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
