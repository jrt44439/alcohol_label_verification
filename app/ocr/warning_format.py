"""27 CFR 16.21 requires the "GOVERNMENT WARNING" heading specifically to be
in capital letters and bold type -- separate from checking the warning
statement's *text*, which app.ocr.field_extractors already handles. These
checks look at how the heading is actually printed on the label."""
import re
import string

import cv2
import numpy as np

from app.ocr.engine import OcrResult, WordBox

_HEADING_RE = re.compile(r"government\s+warning", re.IGNORECASE)
_HEADING_WORD_TEXTS = {"GOVERNMENT", "WARNING"}

MIN_BODY_WORDS = 5
BODY_SAMPLE_SIZE = 20
DEFAULT_BOLD_RATIO_THRESHOLD = 1.15


def check_heading_all_caps(raw_text: str) -> bool | None:
    """Whether the literal "GOVERNMENT WARNING" heading appears in all
    capital letters. Returns None if the heading isn't found in the text at
    all (already reflected as NOT_FOUND on the main warning field)."""
    match = _HEADING_RE.search(raw_text)
    if not match:
        return None
    return match.group(0).isupper()


def _is_heading_word(word: WordBox) -> bool:
    return word.text.strip(string.punctuation).upper() in _HEADING_WORD_TEXTS


def _word_ink_density(gray_image: np.ndarray, word: WordBox) -> float | None:
    crop = gray_image[word.top : word.top + word.height, word.left : word.left + word.width]
    if crop.size == 0:
        return None
    _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return float(np.count_nonzero(binary)) / binary.size


def detect_heading_bold(
    gray_image: np.ndarray, ocr_result: OcrResult, ratio_threshold: float = DEFAULT_BOLD_RATIO_THRESHOLD
) -> bool | None:
    """Best-effort heuristic: compares the average ink-pixel density of the
    "GOVERNMENT"/"WARNING" heading words against a sample of other words in
    the same Tesseract text block (the rest of the warning paragraph, which
    per regulation is normal weight). Bold strokes are thicker, so bold text
    has a higher ink-to-background ratio than regular text of the same size.

    Density is computed per-word (each word's own tight bounding box), not
    over one bounding box spanning the sample -- a multi-line union box would
    be diluted by inter-line whitespace and make the comparison unfair.

    Returns None when there isn't enough to compare: the heading can't be
    located, or too few other words are available as a baseline.
    """
    heading_words = [w for w in ocr_result.words if _is_heading_word(w)]
    if not heading_words:
        return None

    heading_block = heading_words[0].block_num
    heading_ids = {id(w) for w in heading_words}
    body_words = [
        w
        for w in ocr_result.words
        if w.block_num == heading_block
        and id(w) not in heading_ids
        and len(w.text.strip(string.punctuation)) >= 3
    ][:BODY_SAMPLE_SIZE]
    if len(body_words) < MIN_BODY_WORDS:
        return None

    heading_densities = [d for w in heading_words if (d := _word_ink_density(gray_image, w)) is not None]
    body_densities = [d for w in body_words if (d := _word_ink_density(gray_image, w)) is not None]
    if not heading_densities or not body_densities:
        return None

    heading_avg = sum(heading_densities) / len(heading_densities)
    body_avg = sum(body_densities) / len(body_densities)
    if body_avg <= 0:
        return None

    return heading_avg >= body_avg * ratio_threshold
