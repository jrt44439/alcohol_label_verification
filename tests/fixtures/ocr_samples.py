"""Sample raw OCR text strings used to unit-test field extractors and
comparison logic without needing real images or Tesseract."""

CLEAN_BOURBON_LABEL = """\
OLD RIDGE
Kentucky Straight Bourbon Whiskey
45% ALC/VOL (90 PROOF)
750 mL
Produced and Bottled by Old Ridge Distillery, Frankfort, KY

GOVERNMENT WARNING: (1) According to the Surgeon General, women should not
drink alcoholic beverages during pregnancy because of the risk of birth
defects. (2) Consumption of alcoholic beverages impairs your ability to
drive a car or operate machinery, and may cause health problems.
"""

NOISY_BOURBON_LABEL = """\
OLD   RIDGE
kentucky straight bourbon whiskey
45 % alc/vol
750ML
Bottled By Old Ridge Distillery,   Frankfort KY

government   warning: (1) according to the surgeon general , women should not
drink alcoholic beverages during pregnancy because of the risk of birth
defects . (2) consumption of alcoholic beverages impairs your ability to
drive a car or operate machinery , and may cause health problems .
"""

IMPORTED_WINE_LABEL = """\
CHATEAU MAISON
Red Wine
12.5% ALC/VOL
750 mL
Imported by Grand Cru Imports, New York, NY
Product of France

GOVERNMENT WARNING: (1) According to the Surgeon General, women should not
drink alcoholic beverages during pregnancy because of the risk of birth
defects. (2) Consumption of alcoholic beverages impairs your ability to
drive a car or operate machinery, and may cause health problems.
"""

ABSENT_FIELDS_LABEL = """\
SOMETHING SOMETHING
A beverage of unknown description
"""

PROOF_ONLY_LABEL = """\
HIGH PLAINS
Vodka
80 PROOF
1.75 L
Distilled by High Plains Spirits, Denver, CO
"""

# Simulates Tesseract inserting a stray blank line inside a wrapped, multi-line
# producer name/address block (a common real-world OCR artifact).
MULTILINE_ADDRESS_LABEL = """\
SUMMIT PEAK
Small Batch Rye Whiskey
47% ALC/VOL
750 mL
Produced and Bottled by

Summit Peak Distillers
123 Mountain Road
Denver, CO 80202

GOVERNMENT WARNING: (1) According to the Surgeon General, women should not
drink alcoholic beverages during pregnancy because of the risk of birth
defects. (2) Consumption of alcoholic beverages impairs your ability to
drive a car or operate machinery, and may cause health problems.
"""
