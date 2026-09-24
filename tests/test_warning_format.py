import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ocr.engine import OcrResult, WordBox
from app.ocr.warning_format import check_heading_all_caps, detect_heading_bold

CANONICAL_WARNING_TEXT = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects."
)


def test_check_heading_all_caps_true():
    assert check_heading_all_caps(CANONICAL_WARNING_TEXT) is True


def test_check_heading_all_caps_false_when_mixed_case():
    mixed = CANONICAL_WARNING_TEXT.replace("GOVERNMENT WARNING", "Government Warning")
    assert check_heading_all_caps(mixed) is False


def test_check_heading_all_caps_none_when_absent():
    assert check_heading_all_caps("This label has no warning text at all.") is None


BODY_WORDS = ["according", "surgeon", "general", "women", "should", "pregnancy", "because"]


def _render_words(heading_font_name: str, body_font_name: str) -> tuple[np.ndarray, list[WordBox]]:
    img = Image.new("L", (700, 140), color=255)
    draw = ImageDraw.Draw(img)
    heading_font = ImageFont.truetype(heading_font_name, 30)
    body_font = ImageFont.truetype(body_font_name, 30)

    words = []

    x, y = 10, 10
    for text in ("GOVERNMENT", "WARNING:"):
        bbox = draw.textbbox((x, y), text, font=heading_font)
        draw.text((x, y), text, font=heading_font, fill=0)
        left, top, right, bottom = bbox
        words.append(
            WordBox(text=text, conf=95, left=left, top=top, width=right - left, height=bottom - top, block_num=1, line_num=1)
        )
        x = right + 15

    x, y = 10, 70
    for text in BODY_WORDS:
        bbox = draw.textbbox((x, y), text, font=body_font)
        draw.text((x, y), text, font=body_font, fill=0)
        left, top, right, bottom = bbox
        words.append(
            WordBox(text=text, conf=95, left=left, top=top, width=right - left, height=bottom - top, block_num=1, line_num=2)
        )
        x = right + 12

    return np.array(img), words


def test_detect_heading_bold_true_when_heading_is_bold():
    gray, words = _render_words("arialbd.ttf", "arial.ttf")
    ocr_result = OcrResult(raw_text="", words=words)
    assert detect_heading_bold(gray, ocr_result) is True


def test_detect_heading_bold_false_when_heading_is_regular_weight():
    gray, words = _render_words("arial.ttf", "arial.ttf")
    ocr_result = OcrResult(raw_text="", words=words)
    assert detect_heading_bold(gray, ocr_result) is False


def test_detect_heading_bold_none_when_heading_not_found():
    ocr_result = OcrResult(
        raw_text="",
        words=[WordBox(text="hello", conf=95, left=0, top=0, width=40, height=20, block_num=1, line_num=1)],
    )
    assert detect_heading_bold(np.full((100, 100), 255, dtype=np.uint8), ocr_result) is None


def test_detect_heading_bold_none_when_not_enough_body_words():
    ocr_result = OcrResult(
        raw_text="",
        words=[
            WordBox(text="GOVERNMENT", conf=95, left=0, top=0, width=100, height=30, block_num=1, line_num=1),
            WordBox(text="WARNING", conf=95, left=110, top=0, width=80, height=30, block_num=1, line_num=1),
        ],
    )
    assert detect_heading_bold(np.full((100, 300), 255, dtype=np.uint8), ocr_result) is None
