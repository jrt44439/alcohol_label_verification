"""Normalization helpers so extracted and expected values can be compared
on equal footing regardless of formatting differences (units, punctuation,
case, whitespace)."""
import re
import string

_VOLUME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(m\.?l\.?|liters?|litres?|l|fl\.?\s?oz\.?)",
    re.IGNORECASE,
)

_ML_PER_UNIT = {
    "ml": 1.0,
    "l": 1000.0,
    "flooz": 29.5735,  # normalized key after stripping punctuation/spaces
}

_ABV_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE)
_ABV_PROOF_RE = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*PROOF", re.IGNORECASE)

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_text(s: str | None) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for fuzzy text comparison."""
    if not s:
        return ""
    s = s.lower().translate(_PUNCT_TABLE)
    return re.sub(r"\s+", " ", s).strip()


def _unit_key(unit: str) -> str:
    unit = unit.lower().replace(".", "").replace(" ", "")
    if unit.startswith("floz"):
        return "flooz"
    if unit.startswith("l"):
        return "l"
    return "ml"


def normalize_volume(s: str | None) -> float | None:
    """Parse a volume+unit string and return the equivalent value in milliliters."""
    if not s:
        return None
    match = _VOLUME_RE.search(s)
    if not match:
        return None
    value = float(match.group(1))
    unit_key = _unit_key(match.group(2))
    return value * _ML_PER_UNIT[unit_key]


def normalize_abv(s: str | None) -> tuple[float | None, float | None]:
    """Parse an ABV string and return (percent_abv, proof), deriving one from
    the other when only a single form is present."""
    if not s:
        return (None, None)
    pct_match = _ABV_PERCENT_RE.search(s)
    proof_match = _ABV_PROOF_RE.search(s)

    pct = float(pct_match.group(1)) if pct_match else None
    proof = float(proof_match.group(1)) if proof_match else None

    if pct is None and proof is not None:
        pct = proof / 2.0
    if proof is None and pct is not None:
        proof = pct * 2.0

    return (pct, proof)
