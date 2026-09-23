"""Field extraction from reference-document text (spec sheets, COLA-style
forms). Unlike a photographed label, these documents usually have explicit
labeled fields ("Brand Name:", "Net Contents:", ...), so we try a labeled-field
match first and fall back to the same free-text heuristics used for OCR'd
label photos."""
import re

from app.ocr import field_extractors as ocr_field_extractors

LABELED_FIELD_PATTERNS = {
    "brand_name": [r"BRAND\s*NAME", r"BRAND"],
    "class_type": [r"CLASS\s*(?:AND|/)?\s*TYPE", r"TYPE\s*OF\s*PRODUCT", r"CLASS"],
    "alcohol_content": [r"ALCOHOL\s*CONTENT", r"ALC(?:OHOL)?\.?\s*(?:BY|/)?\s*VOL(?:UME)?"],
    "net_contents": [r"NET\s*CONTENTS?"],
    "producer_info": [r"NAME\s*AND\s*ADDRESS\s*OF\s*(?:PRODUCER|BOTTLER|IMPORTER)", r"PRODUCER", r"BOTTLER"],
    "country_of_origin": [r"COUNTRY\s*OF\s*ORIGIN"],
}


def extract_labeled_field(text: str, label_patterns: list[str]) -> str | None:
    for pattern in label_patterns:
        match = re.search(pattern + r"\s*[:\-]\s*(.+)", text, re.IGNORECASE)
        if match:
            value = match.group(1).splitlines()[0].strip()
            if value:
                return value
    return None


def extract_all_fields_from_document(text: str) -> dict[str, str | None]:
    brand_name = extract_labeled_field(text, LABELED_FIELD_PATTERNS["brand_name"])

    class_type = extract_labeled_field(text, LABELED_FIELD_PATTERNS["class_type"])
    if not class_type:
        class_type = ocr_field_extractors.extract_class_type(text)

    alcohol_content = extract_labeled_field(text, LABELED_FIELD_PATTERNS["alcohol_content"])
    if not alcohol_content:
        alcohol_content = ocr_field_extractors.extract_abv(text)

    net_contents = extract_labeled_field(text, LABELED_FIELD_PATTERNS["net_contents"])
    if not net_contents:
        net_contents = ocr_field_extractors.extract_net_contents(text)

    producer_info = extract_labeled_field(text, LABELED_FIELD_PATTERNS["producer_info"])
    if not producer_info:
        producer_info = ocr_field_extractors.extract_producer_info(text)

    country_of_origin = extract_labeled_field(text, LABELED_FIELD_PATTERNS["country_of_origin"])
    if not country_of_origin:
        country_of_origin = ocr_field_extractors.extract_country_of_origin(text)

    return {
        "brand_name": brand_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
        "producer_info": producer_info,
        "country_of_origin": country_of_origin,
    }
