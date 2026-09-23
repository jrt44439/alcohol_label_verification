import pytest

from app.comparison.normalize import normalize_abv, normalize_text, normalize_volume


def test_normalize_text_collapses_whitespace_and_punctuation():
    assert normalize_text("  Old   Ridge, Inc.  ") == "old ridge inc"


def test_normalize_text_none_and_empty():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


@pytest.mark.parametrize(
    "value",
    ["750mL", "750 mL", "750 ML", "750ml", "0.75 L", "0.75L"],
)
def test_normalize_volume_equivalent_forms(value):
    assert normalize_volume(value) == pytest.approx(750.0, abs=0.01)


def test_normalize_volume_fl_oz():
    # 25.4 fl oz ~= 750 mL
    assert normalize_volume("25.4 FL OZ") == pytest.approx(751.17, abs=1.0)


def test_normalize_volume_none_and_unparseable():
    assert normalize_volume(None) is None
    assert normalize_volume("a lot") is None


@pytest.mark.parametrize(
    "value,expected_pct",
    [
        ("45% ALC/VOL", 45.0),
        ("90 PROOF", 45.0),
        ("45% ALC/VOL (90 PROOF)", 45.0),
    ],
)
def test_normalize_abv_pct_and_proof_are_equivalent(value, expected_pct):
    pct, proof = normalize_abv(value)
    assert pct == pytest.approx(expected_pct)
    assert proof == pytest.approx(expected_pct * 2)


def test_normalize_abv_none():
    assert normalize_abv(None) == (None, None)
    assert normalize_abv("no numbers here") == (None, None)
