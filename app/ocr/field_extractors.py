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
from app.ocr.layout import cluster_lines, group_words_by_line

_ABV_PERCENT_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%\s*ALC(?:OHOL)?\.?\s*(?:BY|/)\s*VOL\.?",
    re.IGNORECASE,
)
# Some labels print "ALC." or "ALC./VOL." (or "ALCOHOL BY VOLUME:") *before*
# the percentage instead of after it -- e.g. "ALC. 12%", "ALC./VOL. 45%".
_ABV_PERCENT_ALC_FIRST_RE = re.compile(
    r"ALC(?:OHOL)?\.?(?:\s*(?:BY\s*)?/?\s*VOL(?:UME)?\.?)?\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)\s*%",
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

# Base spirit/wine category words that can follow a more specific class/type
# keyword (e.g. "Kentucky Straight Bourbon" + "Whiskey"), so the extracted
# value isn't truncated to just the specific part.
_CLASS_TYPE_SUFFIX_WORDS = {
    "whiskey", "whisky", "wine", "rum", "gin", "vodka", "tequila", "brandy",
    "liqueur", "cordial", "beer", "ale", "lager", "cider", "mezcal",
}

_CLASS_TYPE_LABEL_PREFIX_RE = re.compile(
    r"^\s*(?:CLASS\s*(?:AND|/)?\s*TYPE(?:\s*OF\s*PRODUCT)?|TYPE\s*OF\s*PRODUCT|CLASS)\s*[:\-]?\s*",
    re.IGNORECASE,
)

# Some COLA application forms present the broad product category as
# checkboxes ("[ ] WINE  [X] DISTILLED SPIRITS  [ ] MALT BEVERAGE") rather
# than free text -- an "X" mark (plain, or in a bracket/parenthesis box)
# sitting right in front of one of the three category words is what was
# actually selected; the unchecked boxes and brackets around it aren't part
# of the value.
_CHECKBOX_CLASS_TYPE_RE = re.compile(
    r"[\[\(]?\b[Xx☒☑][\]\)]?\s*[:\-]?\s*(WINE|DISTILLED\s+SPIRITS|MALT\s+BEVERAGE)\b",
    re.IGNORECASE,
)

# Exhibit/attachment annotations (e.g. "(Front Label)") that sometimes get
# swept into a captured value's trailing edge.
_TRAILING_LABEL_NOISE_RE = re.compile(
    r"\s*[\(\[]?\s*(?:FRONT|BACK|SIDE|NECK|MAIN)(?:\s+LABEL)?\s*[\)\]]?\s*$",
    re.IGNORECASE,
)

# A producer/bottler/importer designation phrase (e.g. "Bottled by",
# "Imported by", "Distilled and Bottled by") -- these anchor where the
# producer_info field is on the label, but aren't part of the actual
# name/address value, so they're stripped off before it's returned/compared.
_PRODUCER_KEYWORD_PREFIX_RE = re.compile(
    r"\b(?:PRODUCED|BOTTLED|DISTILLED|IMPORTED|VINTED|BREWED|CANNED|PACKED)"
    r"(?:\s+AND\s+(?:PRODUCED|BOTTLED|DISTILLED|IMPORTED|VINTED|BREWED|CANNED|PACKED))*"
    r"\s+BY\b\s*[:\-]?\s*",
    re.IGNORECASE,
)

_ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
_US_STATE_RE = re.compile(
    r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|"
    r"NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b"
)
# Full state names (an address may spell the state out instead of using its
# 2-letter abbreviation), plus DC.
_US_STATE_FULL_NAME_RE = re.compile(
    r"\b(?:ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|"
    r"GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|"
    r"MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|"
    r"NEW\s+HAMPSHIRE|NEW\s+JERSEY|NEW\s+MEXICO|NEW\s+YORK|NORTH\s+CAROLINA|NORTH\s+DAKOTA|OHIO|"
    r"OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s+ISLAND|SOUTH\s+CAROLINA|SOUTH\s+DAKOTA|TENNESSEE|"
    r"TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s+VIRGINIA|WISCONSIN|WYOMING|"
    r"DISTRICT\s+OF\s+COLUMBIA)\b",
    re.IGNORECASE,
)
_COUNTRY_HINT_RE = re.compile(
    r"\b(?:UNITED\s+STATES(?:\s+OF\s+AMERICA)?|U\.S\.A\.?|USA|CANADA|MEXICO|FRANCE|ITALY|SPAIN|"
    r"GERMANY|SCOTLAND|IRELAND|ENGLAND|WALES|UNITED\s+KINGDOM|AUSTRALIA|CHILE|ARGENTINA|"
    r"NEW\s+ZEALAND|PORTUGAL|GREECE|AUSTRIA|SOUTH\s+AFRICA|JAPAN|BRAZIL|PERU|URUGUAY|CHINA|INDIA|"
    r"POLAND|HUNGARY|CROATIA|SLOVENIA|ROMANIA|BULGARIA|GEORGIA|ISRAEL|LEBANON|MOROCCO|TUNISIA|"
    r"NETHERLANDS|BELGIUM|SWITZERLAND|SWEDEN|NORWAY|DENMARK|FINLAND|RUSSIA|UKRAINE|TURKEY|"
    r"SOUTH\s+KOREA|TAIWAN|THAILAND|VIETNAM|PHILIPPINES|JAMAICA|BARBADOS|CUBA|DOMINICAN\s+REPUBLIC|"
    r"GUATEMALA|COLOMBIA|VENEZUELA|ECUADOR|BOLIVIA|PARAGUAY|CZECH\s+REPUBLIC|SLOVAKIA|SERBIA|"
    r"LUXEMBOURG|MALTA|CYPRUS|ICELAND)\b",
    re.IGNORECASE,
)

# Full state name -> 2-letter abbreviation, so e.g. "Kentucky" and "KY" can
# be recognized as the same state when broadly comparing two addresses.
_STATE_FULL_TO_ABBR = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
}


def find_state_match(value: str) -> re.Match | None:
    """Return the first regex match for a recognized US state (abbreviation
    or full name) found in ``value``, or None."""
    for pattern in (_US_STATE_RE, _US_STATE_FULL_NAME_RE):
        match = pattern.search(value)
        if match:
            return match
    return None


def normalize_state(value: str) -> str | None:
    """Normalize a matched state string (abbreviation or full name) to its
    2-letter abbreviation, so e.g. "Kentucky" and "KY" compare as the same
    state. Returns None if ``value`` isn't a recognized state."""
    key = re.sub(r"\s+", " ", value.strip().upper())
    if key in _STATE_FULL_TO_ABBR:
        return _STATE_FULL_TO_ABBR[key]
    if _US_STATE_RE.fullmatch(key):
        return key
    return None


def normalize_states_in_text(value: str) -> str:
    """Replace every full US state name found in ``value`` with its
    2-letter abbreviation (e.g. "Frankfort, Kentucky" -> "Frankfort, KY"),
    so a plain word/keyword comparison treats them as the same token."""
    def _replace(match: re.Match) -> str:
        key = re.sub(r"\s+", " ", match.group(0).upper())
        return _STATE_FULL_TO_ABBR.get(key, match.group(0))

    return _US_STATE_FULL_NAME_RE.sub(_replace, value)


def strip_class_type_label_prefix(value: str) -> str:
    return _CLASS_TYPE_LABEL_PREFIX_RE.sub("", value).strip()


def strip_trailing_label_noise(value: str) -> str:
    return _TRAILING_LABEL_NOISE_RE.sub("", value).strip()


def strip_producer_keyword_prefix(value: str) -> str:
    """Remove a leading producer/bottler/importer designation phrase (e.g.
    "Bottled by", "Imported by", "Distilled and Bottled by") from a
    captured producer_info value -- it anchors where the field is on the
    label, but isn't itself part of the name/address."""
    return _PRODUCER_KEYWORD_PREFIX_RE.sub("", value, count=1).strip(" ,.-")


def extract_class_type_from_checkbox(text: str) -> str | None:
    """If ``text`` contains a checked ("X"-marked) box in front of Wine,
    Distilled Spirits, or Malt Beverage, return just that category -- not
    the surrounding unchecked boxes/brackets. Returns None if no checked
    box is found."""
    match = _CHECKBOX_CLASS_TYPE_RE.search(text)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip().title()


_ADDRESS_END_PATTERNS = (_ZIP_RE, _US_STATE_RE, _US_STATE_FULL_NAME_RE, _COUNTRY_HINT_RE)


def trim_to_address_end(value: str) -> str:
    """Truncate a captured producer/address value to end at the last zip
    code, US state (abbreviation or full name), or country name found in it
    -- trimming trailing noise (e.g. a form instruction or the start of the
    next field) that got swept in after the real address ended. Any of
    those found *after* the first one just extends where capture stops,
    rather than being trimmed away, since they're still part of the
    address, not noise. Left unchanged if none of those are found, since
    that's not enough to safely guess where the real content ends."""
    last_end = None
    for pattern in _ADDRESS_END_PATTERNS:
        for m in pattern.finditer(value):
            if last_end is None or m.end() > last_end:
                last_end = m.end()
    if last_end is None:
        return value
    return value[:last_end].strip(" ,.-")


def looks_like_address_end(line: str) -> bool:
    """Whether ``line`` contains a zip code, US state (abbreviation or full
    name), or recognizable country name -- a strong signal that it's the
    last line of a mailing address, so multi-line capture should stop right
    after it rather than continuing to absorb whatever comes next."""
    return any(pattern.search(line) for pattern in _ADDRESS_END_PATTERNS)


def extract_abv(text: str) -> str | None:
    pct_match = _ABV_PERCENT_RE.search(text) or _ABV_PERCENT_ALC_FIRST_RE.search(text)
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


def _finalize_producer_value(value: str) -> str:
    """Shared cleanup for a captured producer_info value: strip the leading
    designation phrase (e.g. "Bottled by") and trim trailing noise after
    the address ends."""
    if not value:
        return value
    return trim_to_address_end(strip_producer_keyword_prefix(value))


def extract_producer_info(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        upper = line.upper()
        if any(keyword in upper for keyword in PRODUCER_KEYWORDS):
            captured = [line]
            if looks_like_address_end(line):
                # The whole address, including its zip/state/country, was
                # already on this one line -- nothing more to capture.
                value = " ".join(captured).strip()
                return _finalize_producer_value(value)
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
                if looks_like_address_end(follow) or len(captured) >= 5:
                    # Stop right after the line that ends the address (zip/
                    # state/country) -- whatever follows is a different field.
                    break
            value = " ".join(captured).strip()
            return _finalize_producer_value(value)
    return None


def extract_producer_info_from_words(ocr_result: OcrResult) -> str | None:
    """Position-aware variant of extract_producer_info(): finds the anchor
    line via PRODUCER_KEYWORDS, then clusters forward with cluster_lines()
    so only lines that are actually close to *and* a similar font size to
    the anchor get pulled in as the address -- e.g. separate, smaller-font
    fine print sitting right below the address no longer gets swept in the
    way a blind "grab up to 5 following text lines" could. Falls back to
    None (letting the caller try the plain-text extractor) if no anchor
    line is found in the word-position data.

    The producer/bottler/importer line is frequently the smallest,
    densest-packed text on the whole label (government-mandated fine
    print), so the cluster search here uses a wider gap tolerance and a
    higher line cap than the general-purpose default -- a wrapped
    small-print address can run several lines long with tighter line
    spacing than body text. The height ratio guard is left at its default,
    though: it's what tells a same-field wrapped line (always close to the
    same size) apart from genuinely different, smaller-font text like a
    separate fine-print disclaimer sitting right below it."""
    line_info = group_words_by_line(ocr_result.words)
    if not line_info:
        return None

    # Top-to-bottom, then left-to-right reading order.
    ordered_keys = sorted(line_info, key=lambda k: (line_info[k]["top"], line_info[k]["left"]))

    for key in ordered_keys:
        upper = line_info[key]["text"].upper()
        if not any(keyword in upper for keyword in PRODUCER_KEYWORDS):
            continue

        cluster = cluster_lines(line_info, key, max_lines=8, max_gap_ratio=2.2)
        captured = []
        for cluster_key in cluster:
            line_text = line_info[cluster_key]["text"]
            line_upper = line_text.upper()
            if cluster_key != key and any(keyword in line_upper for keyword in PRODUCER_KEYWORDS):
                break
            if "GOVERNMENT WARNING" in line_upper or "PRODUCT OF" in line_upper:
                break
            captured.append(line_text)
            if looks_like_address_end(line_text):
                break

        value = " ".join(captured).strip()
        return _finalize_producer_value(value)

    return None


def extract_country_of_origin(text: str) -> str | None:
    match = _COUNTRY_RE.search(text)
    if not match:
        return None
    country = match.group(1).strip()
    # Trim anything captured past the country name (e.g. trailing OCR noise/newlines).
    country = re.split(r"\s{2,}|[\r\n]", country)[0].strip(" .,")
    return country or None


def _keyword_regex(keyword: str) -> re.Pattern:
    """A regex matching ``keyword``'s words in order, allowing a short run of
    whitespace (including a newline) between them -- so a multi-word class/
    type designation is still found when the label prints it across two
    lines, without matching if unrelated words sit in between."""
    parts = [re.escape(w) for w in keyword.split()]
    return re.compile(r"\s{1,20}".join(parts), re.IGNORECASE)


def extract_class_type(text: str) -> str | None:
    best_match = None
    best_regex = None
    for keyword in sorted(CLASS_TYPE_KEYWORDS, key=len, reverse=True):
        regex = _keyword_regex(keyword)
        if regex.search(text):
            best_match = keyword
            best_regex = regex
            break
    if best_match is None:
        return None

    # Extract a bounded snippet around the matched keyword (e.g. "Kentucky
    # Straight Bourbon" plus a following base-category word like "Whiskey")
    # rather than the whole line -- a label's class/type text can otherwise
    # run into unrelated neighboring words, and multi-word designations can
    # legitimately span two printed (and so two OCR'd text) lines.
    match = best_regex.search(text)
    snippet = re.sub(r"\s+", " ", match.group(0)).strip()

    rest = text[match.end() :]
    suffix_match = re.match(r"\s+([A-Za-z]+)", rest)
    if suffix_match and suffix_match.group(1).lower() in _CLASS_TYPE_SUFFIX_WORDS:
        snippet += " " + suffix_match.group(1)

    snippet = strip_trailing_label_noise(strip_class_type_label_prefix(snippet))
    return snippet or best_match.title()


def extract_health_warning(text: str) -> str | None:
    match = _WARNING_RE.search(text)
    if not match:
        return None
    return " ".join(match.group(0).split())


def extract_brand_name(ocr_result: OcrResult) -> str | None:
    """Best-effort heuristic: the tallest text line that isn't one of the
    other mandatory fields, preferring lines nearer the top of the image.
    Nearby lines of a similar height are clustered in too, so a multi-line
    brand name (e.g. a logo) isn't truncated to just one line -- but a
    same-height line separated by a large vertical gap (a visually
    unrelated block of text) is not.

    The clustering search scans a wide area: the whole page's line order
    (not just one Tesseract block, since a logo can get split across
    blocks), a generous gap tolerance (more breathing room between lines
    than body text usually has), and -- since the single tallest line isn't
    always the *first* line of a multi-line brand name (a smaller-font
    line, e.g. a tagline, can sit above the tallest one) -- both above and
    below the tallest line, not just downward."""
    line_info = {
        key: line
        for key, line in group_words_by_line(ocr_result.words).items()
        if not _EXCLUDE_FROM_BRAND_RE.search(line["text"])
    }

    if not line_info:
        return None

    # Prefer the tallest line; break ties by favoring lines closer to the top.
    tallest_key = max(line_info, key=lambda k: (line_info[k]["height"], -line_info[k]["top"]))

    below = cluster_lines(line_info, tallest_key, max_lines=4, max_gap_ratio=2.5)
    above = cluster_lines(line_info, tallest_key, max_lines=4, max_gap_ratio=2.5, direction=-1)
    cluster = above[:-1] + below  # `above` already ends with tallest_key -- don't duplicate it.
    return " ".join(line_info[key]["text"] for key in cluster)


def extract_all_fields(ocr_result: OcrResult) -> dict[str, str | None]:
    text = ocr_result.raw_text
    return {
        "brand_name": extract_brand_name(ocr_result),
        "class_type": extract_class_type(text),
        "alcohol_content": extract_abv(text),
        "net_contents": extract_net_contents(text),
        # Position-aware extraction is more reliable (font-size/proximity
        # aware) but depends on confidence-filtered word data; fall back to
        # the plain-text version if it can't find an anchor.
        "producer_info": extract_producer_info_from_words(ocr_result) or extract_producer_info(text),
        "country_of_origin": extract_country_of_origin(text),
        "health_warning_text": extract_health_warning(text),
    }
