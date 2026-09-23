"""Heuristic extraction of the 7 mandatory label fields from raw OCR output.

Each ``extract_*`` function is a pure function operating on plain text (or, for
brand name, on the word/position data in an :class:`~app.ocr.engine.OcrResult`),
so they can be unit-tested with string fixtures with no image or Tesseract
dependency. None of these are expected to be perfect -- the web UI always lets
the user review the raw OCR text and correct any field before comparison.
"""
import re

from config import CLASS_TYPE_KEYWORDS, PRODUCER_KEYWORDS
from app.ocr.engine import OcrResult

_ABV_PERCENT_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%\s*ALC(?:OHOL)?\.?\s*(?:BY|/)\s*VOL\.?",
    re.IGNORECASE,
)
_ABV_PROOF_RE = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*PROOF", re.IGNORECASE)

_NET_CONTENTS_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(m\.?l\.?|liters?|litres?|l|fl\.?\s?oz\.?)\b",
    re.IGNORECASE,
)

_COUNTRY_RE = re.compile(r"PRODUCT\s+OF\s+([A-Za-z][A-Za-z\s]{1,40})", re.IGNORECASE)

_WARNING_RE = re.compile(r"GOVERNMENT\s+WARNING.{0,600}", re.IGNORECASE | re.DOTALL)

_EXCLUDE_FROM_BRAND_RE = re.compile(
    r"GOVERNMENT WARNING|PRODUCED|BOTTLED|IMPORTED|DISTILLED|VINTED|BREWED|"
    r"PRODUCT OF|PROOF|ALC|VOL|%",
    re.IGNORECASE,
)


def extract_abv(text: str) -> str | None:
    pct_match = _ABV_PERCENT_RE.search(text)
    proof_match = _ABV_PROOF_RE.search(text)
    if pct_match and proof_match:
        return f"{pct_match.group(1)}% ALC/VOL ({proof_match.group(1)} PROOF)"
    if pct_match:
        return f"{pct_match.group(1)}% ALC/VOL"
    if proof_match:
        return f"{proof_match.group(1)} PROOF"
    return None


def extract_net_contents(text: str) -> str | None:
    match = _NET_CONTENTS_RE.search(text)
    if not match:
        return None
    value, unit = match.group(1), match.group(2)
    return f"{value} {unit}".strip()


def extract_producer_info(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        upper = line.upper()
        if any(keyword in upper for keyword in PRODUCER_KEYWORDS):
            captured = [line]
            blank_run = 0
            for follow in lines[i + 1 : i + 8]:
                if not follow:
                    # Tesseract sometimes inserts a stray blank line in the
                    # middle of a wrapped multi-line name/address; tolerate
                    # one, but two in a row is a genuine paragraph break.
                    blank_run += 1
                    if blank_run >= 2:
                        break
                    continue
                blank_run = 0
                follow_upper = follow.upper()
                if any(keyword in follow_upper for keyword in PRODUCER_KEYWORDS):
                    break
                if "GOVERNMENT WARNING" in follow_upper or "PRODUCT OF" in follow_upper:
                    break
                captured.append(follow)
                if len(captured) >= 5:
                    break
            return " ".join(captured).strip()
    return None


def extract_country_of_origin(text: str) -> str | None:
    match = _COUNTRY_RE.search(text)
    if not match:
        return None
    country = match.group(1).strip()
    # Trim anything captured past the country name (e.g. trailing OCR noise/newlines).
    country = re.split(r"\s{2,}|[\r\n]", country)[0].strip(" .,")
    return country or None


def extract_class_type(text: str) -> str | None:
    lower = text.lower()
    best_match = None
    for keyword in sorted(CLASS_TYPE_KEYWORDS, key=len, reverse=True):
        if keyword in lower:
            best_match = keyword
            break
    if best_match is None:
        return None

    # Return the whole line the keyword was found on (e.g. "Kentucky Straight
    # Bourbon Whiskey") rather than just the matched keyword ("Bourbon"), so
    # multi-word class/type designations aren't truncated to a single word.
    for line in text.splitlines():
        if best_match in line.lower():
            cleaned = line.strip()
            if cleaned:
                return cleaned

    return best_match.title()


def extract_health_warning(text: str) -> str | None:
    match = _WARNING_RE.search(text)
    if not match:
        return None
    return " ".join(match.group(0).split())


def extract_brand_name(ocr_result: OcrResult) -> str | None:
    """Best-effort heuristic: the tallest text line that isn't one of the
    other mandatory fields, preferring lines nearer the top of the image.
    If the very next line in the same block is a similar height, it's merged
    in too, so a brand name stacked across two lines (e.g. a logo) isn't
    truncated to just its first line."""
    lines: dict[tuple[int, int], list] = {}
    for word in ocr_result.words:
        key = (word.block_num, word.line_num)
        lines.setdefault(key, []).append(word)

    line_info = {}
    for key, words in lines.items():
        words.sort(key=lambda w: w.left)
        line_text = " ".join(w.text for w in words)
        if not line_text.strip() or _EXCLUDE_FROM_BRAND_RE.search(line_text):
            continue
        avg_height = sum(w.height for w in words) / len(words)
        top = min(w.top for w in words)
        line_info[key] = {"text": line_text.strip(), "height": avg_height, "top": top}

    if not line_info:
        return None

    # Prefer the tallest line; break ties by favoring lines closer to the top.
    tallest_key = max(line_info, key=lambda k: (line_info[k]["height"], -line_info[k]["top"]))
    tallest = line_info[tallest_key]

    merged = [tallest["text"]]
    next_key = (tallest_key[0], tallest_key[1] + 1)
    next_line = line_info.get(next_key)
    if next_line is not None and next_line["height"] >= tallest["height"] * 0.6:
        merged.append(next_line["text"])

    return " ".join(merged)


def extract_all_fields(ocr_result: OcrResult) -> dict[str, str | None]:
    text = ocr_result.raw_text
    return {
        "brand_name": extract_brand_name(ocr_result),
        "class_type": extract_class_type(text),
        "alcohol_content": extract_abv(text),
        "net_contents": extract_net_contents(text),
        "producer_info": extract_producer_info(text),
        "country_of_origin": extract_country_of_origin(text),
        "health_warning_text": extract_health_warning(text),
    }
