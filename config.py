"""Application configuration and shared constants."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# The federally mandated Government Health Warning statement (27 CFR 16.21).
CANONICAL_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# Alcohol class/type keywords used by the class/type extractor.
CLASS_TYPE_KEYWORDS = [
    "bourbon", "scotch", "whiskey", "whisky", "rye", "vodka", "gin", "rum",
    "tequila", "mezcal", "brandy", "cognac", "liqueur", "cordial", "wine",
    "champagne", "sparkling wine", "cider", "beer", "ale", "lager", "stout",
    "porter", "malt beverage", "vermouth", "sake",
]

# Keywords that anchor the producer/bottler/importer line.
PRODUCER_KEYWORDS = [
    "PRODUCED BY", "PRODUCED AND BOTTLED BY", "DISTILLED BY", "DISTILLED AND BOTTLED BY",
    "BOTTLED BY", "IMPORTED BY", "VINTED BY", "BREWED BY",
]


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    DATABASE = os.environ.get("DATABASE", os.path.join(BASE_DIR, "instance", "app.sqlite3"))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024  # 60 MB max upload (batch of several label photos)
    TESSERACT_CMD = os.environ.get("TESSERACT_CMD")  # e.g. C:\Program Files\Tesseract-OCR\tesseract.exe

    # Comparison thresholds / tolerances.
    TEXT_MATCH_THRESHOLD = 85       # rapidfuzz token_sort_ratio (0-100) for brand/class/producer/country
    WARNING_MATCH_THRESHOLD = 80    # lower threshold: long paragraph accumulates more OCR noise
    ABV_TOLERANCE_PCT = 0.3         # absolute percentage points of ABV tolerance
    VOLUME_TOLERANCE_PCT = 1.0      # percent tolerance on normalized mL volume

    # OCR
    OCR_MIN_CONFIDENCE = 30         # discard low-confidence words before field extraction
    # --psm 4: assume a single column of text of variable sizes -- fits a bottle
    # label's mostly top-to-bottom layout while tolerating the brand name, fine
    # print, and warning paragraph all being wildly different font sizes.
    # --oem 3: use Tesseract's default (LSTM) engine.
    # Override via the TESSERACT_CONFIG env var to try other PSM modes (e.g.
    # "--oem 3 --psm 11" for sparse/scattered text) if a particular label's
    # layout still reads poorly.
    TESSERACT_CONFIG = os.environ.get("TESSERACT_CONFIG", "--oem 3 --psm 4")
