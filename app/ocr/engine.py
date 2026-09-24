"""Runs Tesseract OCR over a preprocessed image and returns structured results."""
from dataclasses import dataclass, field

import numpy as np
import pytesseract
from pytesseract import Output


@dataclass
class WordBox:
    text: str
    conf: float
    left: int
    top: int
    width: int
    height: int
    block_num: int
    line_num: int
    par_num: int = 1


@dataclass
class OcrResult:
    raw_text: str
    words: list[WordBox] = field(default_factory=list)


def configure_tesseract(cmd: str | None) -> None:
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def run_ocr(image: np.ndarray, min_confidence: int = 30, config: str = "") -> OcrResult:
    """Run Tesseract over a preprocessed (numpy array) image.

    ``config`` is a raw Tesseract config string (e.g. "--oem 3 --psm 4")
    controlling page segmentation mode / engine mode -- see config.py's
    TESSERACT_CONFIG for the default and why it was chosen.

    Returns the full unfiltered raw text (for manual review) plus a list of
    word boxes filtered to those at or above ``min_confidence``, used by
    field extractors that rely on position/size (e.g. brand name).
    """
    raw_text = pytesseract.image_to_string(image, config=config)
    data = pytesseract.image_to_data(image, config=config, output_type=Output.DICT)

    words: list[WordBox] = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < min_confidence:
            continue
        words.append(
            WordBox(
                text=text,
                conf=conf,
                left=data["left"][i],
                top=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                block_num=data["block_num"][i],
                line_num=data["line_num"][i],
                par_num=data["par_num"][i],
            )
        )

    return OcrResult(raw_text=raw_text, words=words)
