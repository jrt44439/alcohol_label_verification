"""Field extraction from reference-document text (spec sheets, COLA-style
forms). Unlike a photographed label, these documents usually have explicit
labeled fields ("Brand Name:", "Net Contents:", ...), so we try a labeled-field
match first and fall back to the same free-text heuristics used for OCR'd
label photos.

Real form text (e.g. a COLA application extracted from a fillable PDF) very
often prints a field's label on its own line, with the filled-in value on the
line(s) below -- not "Label: value" on one line -- so the labeled-field match
below tries both layouts.
"""
import re

from app.ocr import field_extractors as ocr_field_extractors

LABELED_FIELD_PATTERNS = {
    "brand_name": [r"BRAND\s*NAME", r"BRAND"],
    "class_type": [r"CLASS\s*(?:AND|/)?\s*TYPE", r"TYPE\s*OF\s*PRODUCT", r"CLASS"],
    "alcohol_content": [r"ALCOHOL\s*CONTENT", r"ALC(?:OHOL)?\.?\s*(?:BY|/)?\s*VOL(?:UME)?"],
    "net_contents": [r"NET\s*CONTENTS?"],
    "producer_info": [
        r"NAME\s+(?:AND|&)\s+ADDRESS\s+OF\s+(?:THE\s+)?(?:PRODUCER|BOTTLER|IMPORTER|PERMITTEE|APPLICANT)"
        r"(?:[,/]?\s*(?:AND|OR)?\s*(?:PRODUCER|BOTTLER|IMPORTER|PERMITTEE|APPLICANT))*",
        # Fallback: some forms head this field just "Name and Address"
        # without "...of Producer/Bottler/Importer/Applicant" attached.
        r"NAME\s+(?:AND|&)\s+ADDRESS",
    ],
    "country_of_origin": [r"COUNTRY\s*OF\s*ORIGIN"],
}

# Defensive cleanup in case a captured value still starts with the label
# itself (e.g. a document quirk not caught by the match-consumes-the-label
# logic in extract_labeled_field below). Covers both the full "...of
# Producer/Bottler/Importer/Applicant" heading and the bare "Name and
# Address" form.
_PRODUCER_LABEL_PREFIX_RE = re.compile(
    r"^\s*NAME\s+(?:AND|&)\s+ADDRESS"
    r"(?:\s+OF\s+(?:THE\s+)?(?:PRODUCER|BOTTLER|IMPORTER|PERMITTEE|APPLICANT)"
    r"(?:[,/]?\s*(?:AND|OR)?\s*(?:PRODUCER|BOTTLER|IMPORTER|PERMITTEE|APPLICANT))*)?"
    r"\s*[:\-]?\s*",
    re.IGNORECASE,
)


def _strip_producer_label_prefix(value: str) -> str:
    return _PRODUCER_LABEL_PREFIX_RE.sub("", value).strip()

# A numbered/lettered form field, e.g. "7.", "(10)", or a sub-item like
# "8A." -- the letter suffix matters so a sub-item heading (e.g. "8A.
# MAILING ADDRESS" right after an "8. Name and Address..." field) is still
# recognized as the start of a different field, not absorbed into it.
_NUMBERED_FIELD_RE = re.compile(r"^\s*\(?\d{1,2}[A-Za-z]?[\.\)]\s")

_ALL_LABEL_REGEXES = [
    re.compile(pattern, re.IGNORECASE)
    for patterns in LABELED_FIELD_PATTERNS.values()
    for pattern in patterns
]


def _looks_like_field_heading(line: str) -> bool:
    """Whether ``line`` looks like the start of a different form field, so
    multi-line value capture should stop before it rather than absorbing it."""
    stripped = line.strip()
    if not stripped:
        return False
    if _NUMBERED_FIELD_RE.match(stripped):
        return True
    if any(r.search(stripped) for r in _ALL_LABEL_REGEXES):
        return True
    letters = [c for c in stripped if c.isalpha()]
    # A short, fully-uppercase line reads as a heading rather than a filled-in
    # answer (a real producer name/address is rarely written in all caps).
    return len(letters) >= 4 and all(c.isupper() for c in letters) and len(stripped) <= 80


def extract_labeled_field(
    text: str,
    label_patterns: list[str],
    multiline: bool = False,
    max_lines: int = 4,
    stop_at_address_end: bool = False,
) -> str | None:
    """Find a form-style labeled field and return its value.

    Handles both "Label: value" on one line and the label alone on its own
    line with the value on the following line(s) (common in text extracted
    from a fillable PDF form). ``multiline`` collects several following lines
    (e.g. a wrapped producer address) instead of just one; either way, capture
    stops at the next recognizable field heading so it never absorbs
    unrelated content below. ``stop_at_address_end`` additionally stops
    capture right after a line containing a zip/state/country -- only
    appropriate for an address-shaped field (e.g. producer_info); a state
    name can be an ordinary word elsewhere (e.g. "Kentucky Straight Bourbon
    Whiskey" for class_type), so this must not be applied generically.
    """
    lines = text.splitlines()
    for pattern in label_patterns:
        label_re = re.compile(pattern, re.IGNORECASE)
        for i, line in enumerate(lines):
            match = label_re.search(line)
            if not match:
                continue

            after = line[match.end() :]
            # Strip an inline parenthetical instruction (e.g. "...Importer
            # (Include Plant Registry/Basic Permit Number): value") before
            # deciding whether what follows is a real "label: value"
            # separator -- otherwise it looks like unrelated sentence text
            # and the real value gets missed.
            after_for_check = re.sub(r"\([^)]*\)", " ", after)

            # Same line, explicitly separated: "Label: value" / "Label - value".
            colon_match = re.match(r"\s*[:\-]\s*(.+)", after_for_check)
            if colon_match:
                value = re.sub(r"\([^)]*\)", "", colon_match.group(1)).strip()
                if value:
                    return value
                continue

            trailing = after_for_check.strip(" \t:-.,")
            if trailing:
                trailing_letters = [c for c in trailing if c.isalpha()]
                looks_like_more_heading = bool(trailing_letters) and all(c.isupper() for c in trailing_letters)
                if not looks_like_more_heading:
                    # Something other than trailing punctuation follows the
                    # match on the same line without a separator, and it
                    # reads like natural sentence text (e.g. "...at 45%
                    # ALC/VOL in 750 mL...") rather than more heading words
                    # -- the pattern matched inside a sentence, not a real
                    # form label. Don't treat the rest as a value.
                    continue
                # Otherwise it's just more heading text in caps (e.g. "8.
                # NAME AND ADDRESS OF APPLICANT AS SHOWN ON PERMIT OR
                # BREWER'S NOTICE") -- fall through to capture the real
                # value from the line(s) below instead of rejecting the
                # match.

            # The label is essentially the whole line -- the filled-in value
            # is on the line(s) below, a common fillable-PDF-form layout.
            captured = []
            limit = max_lines if multiline else 1
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1  # skip blank spacing between the label and its value

            blank_run = 0
            while j < len(lines) and len(captured) < limit:
                follow = lines[j].strip()
                j += 1
                if not follow:
                    # Tolerate one stray blank line inside a wrapped value
                    # (common PDF-extraction artifact); two in a row is a
                    # genuine end of this field's content.
                    blank_run += 1
                    if blank_run >= 2:
                        break
                    continue
                blank_run = 0
                if follow.startswith("(") and follow.endswith(")"):
                    # A parenthetical form instruction, not part of the value.
                    continue
                if _looks_like_field_heading(follow):
                    break
                captured.append(follow)
                if stop_at_address_end and ocr_field_extractors.looks_like_address_end(follow):
                    # A zip code, state, or country is a strong signal this
                    # line ends the address -- stop here rather than
                    # continuing into whatever field comes next, even if it
                    # isn't a heading pattern we recognize.
                    break

            value = " ".join(captured).strip()
            if value:
                return value
            # Matched the label here but found no usable value -- keep
            # scanning in case the same phrase appears again elsewhere.
    return None


def extract_all_fields_from_document(text: str) -> dict[str, str | None]:
    brand_name = extract_labeled_field(text, LABELED_FIELD_PATTERNS["brand_name"])
    brand_name = ocr_field_extractors.strip_trailing_label_noise(brand_name) if brand_name else brand_name

    # multiline (capped at 3 lines) so a class/type designation split across
    # two printed lines on the form (e.g. "Kentucky Straight" / "Bourbon
    # Whiskey"), or a checkbox-style "Type of Product" field with one
    # category per line, is still captured whole; capture still stops at
    # the next recognized field heading, so a genuinely single-line value
    # isn't over-captured.
    class_type = extract_labeled_field(text, LABELED_FIELD_PATTERNS["class_type"], multiline=True, max_lines=3)
    if not class_type:
        # A checkbox-only "Type of Product" field (no specific varietal text
        # anywhere) reads as an all-caps line to the heading detector above,
        # so the labeled-field capture above finds no usable value for it --
        # try the checkbox pattern directly on the full text next, before
        # falling back to the freeform keyword search below, which would
        # otherwise just grab whichever category word happens to appear
        # first/longest regardless of which box is actually checked.
        class_type = ocr_field_extractors.extract_class_type_from_checkbox(text)
    if not class_type:
        class_type = ocr_field_extractors.extract_class_type(text)
    if class_type:
        # Some forms present this field as checkboxes ("[ ] WINE [X]
        # DISTILLED SPIRITS [ ] MALT BEVERAGE") rather than free text -- if
        # so, only the checked category is the intended value, not the
        # whole jumbled line of boxes and labels.
        checkbox_category = ocr_field_extractors.extract_class_type_from_checkbox(class_type)
        if checkbox_category:
            class_type = checkbox_category
        class_type = ocr_field_extractors.strip_trailing_label_noise(
            ocr_field_extractors.strip_class_type_label_prefix(class_type)
        )

    alcohol_content = extract_labeled_field(text, LABELED_FIELD_PATTERNS["alcohol_content"])
    if not alcohol_content:
        alcohol_content = ocr_field_extractors.extract_abv(text)
    if alcohol_content:
        alcohol_content = ocr_field_extractors.strip_trailing_label_noise(alcohol_content)

    net_contents = extract_labeled_field(text, LABELED_FIELD_PATTERNS["net_contents"])
    if not net_contents:
        net_contents = ocr_field_extractors.extract_net_contents(text)
    if net_contents:
        net_contents = ocr_field_extractors.strip_trailing_label_noise(net_contents)

    producer_info = extract_labeled_field(
        text, LABELED_FIELD_PATTERNS["producer_info"], multiline=True, stop_at_address_end=True
    )
    if not producer_info:
        producer_info = ocr_field_extractors.extract_producer_info(text)
    if producer_info:
        producer_info = ocr_field_extractors.strip_trailing_label_noise(
            ocr_field_extractors.trim_to_address_end(_strip_producer_label_prefix(producer_info))
        )

    country_of_origin = extract_labeled_field(text, LABELED_FIELD_PATTERNS["country_of_origin"])
    if not country_of_origin:
        country_of_origin = ocr_field_extractors.extract_country_of_origin(text)
    if country_of_origin:
        country_of_origin = ocr_field_extractors.strip_trailing_label_noise(country_of_origin)

    return {
        "brand_name": brand_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
        "producer_info": producer_info,
        "country_of_origin": country_of_origin,
    }
