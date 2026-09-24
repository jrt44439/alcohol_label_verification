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

# Alcohol class/type keywords used by the class/type extractor. Longer/more
# specific phrases are tried first (see extract_class_type's sort by length),
# so e.g. "kentucky straight bourbon" wins over a bare "bourbon" match when
# both are present.
CLASS_TYPE_KEYWORDS = [
    # Base spirit categories.
    "bourbon", "scotch", "whiskey", "whisky", "rye", "vodka", "gin", "rum",
    "tequila", "mezcal", "brandy", "cognac", "liqueur", "cordial", "wine",
    "champagne", "sparkling wine", "cider", "beer", "ale", "lager", "stout",
    "porter", "malt beverage", "vermouth", "sake",
    "red wine", "white wine", "rosé wine", "rose wine", "blush wine",
    "dessert wine", "fortified wine", "table wine",
    # More specific spirits designations.
    "kentucky straight bourbon", "straight bourbon", "straight rye",
    "tennessee whiskey", "single malt scotch", "blended whiskey",
    "irish whiskey", "canadian whisky", "london dry gin", "silver tequila",
    "blanco tequila", "reposado tequila", "reposado", "añejo tequila",
    "anejo tequila", "añejo", "anejo", "spiced rum", "white rum", "dark rum",
    "armagnac",
    # Common wine grape varietals -- these function as the class/type
    # designation on a varietal wine label per 27 CFR Part 4.
    "cabernet sauvignon", "cabernet franc", "sauvignon blanc",
    "pinot grigio", "pinot gris", "pinot noir", "chenin blanc",
    "chardonnay", "merlot", "riesling", "zinfandel", "malbec", "syrah",
    "shiraz", "moscato", "viognier", "grenache", "tempranillo",
    "sangiovese", "nebbiolo",
]

# Maps each specific class/type keyword above (plus the 3 broad category
# names themselves) to its broad TTB product category -- "Wine",
# "Distilled Spirits", or "Malt Beverage" -- an application's Type of
# Product checkbox usually only records the broad category, so a specific
# label designation like "Bourbon Whiskey" or "Chardonnay" needs to be
# compared against it broadly rather than as an exact/fuzzy text match.
CLASS_TYPE_BROAD_CATEGORY = {
    # Distilled spirits.
    "bourbon": "distilled spirits", "scotch": "distilled spirits",
    "whiskey": "distilled spirits", "whisky": "distilled spirits",
    "rye": "distilled spirits", "vodka": "distilled spirits",
    "gin": "distilled spirits", "rum": "distilled spirits",
    "tequila": "distilled spirits", "mezcal": "distilled spirits",
    "brandy": "distilled spirits", "cognac": "distilled spirits",
    "liqueur": "distilled spirits", "cordial": "distilled spirits",
    "armagnac": "distilled spirits",
    "kentucky straight bourbon": "distilled spirits", "straight bourbon": "distilled spirits",
    "straight rye": "distilled spirits", "tennessee whiskey": "distilled spirits",
    "single malt scotch": "distilled spirits", "blended whiskey": "distilled spirits",
    "irish whiskey": "distilled spirits", "canadian whisky": "distilled spirits",
    "london dry gin": "distilled spirits", "silver tequila": "distilled spirits",
    "blanco tequila": "distilled spirits", "reposado tequila": "distilled spirits",
    "reposado": "distilled spirits", "añejo tequila": "distilled spirits",
    "anejo tequila": "distilled spirits", "añejo": "distilled spirits",
    "anejo": "distilled spirits", "spiced rum": "distilled spirits",
    "white rum": "distilled spirits", "dark rum": "distilled spirits",
    "distilled spirits": "distilled spirits",
    # Wine (including TTB-regulated cider, vermouth, and sake).
    "wine": "wine", "champagne": "wine", "sparkling wine": "wine",
    "cider": "wine", "vermouth": "wine", "sake": "wine",
    "red wine": "wine", "white wine": "wine", "rosé wine": "wine",
    "rose wine": "wine", "blush wine": "wine", "dessert wine": "wine",
    "fortified wine": "wine", "table wine": "wine",
    "cabernet sauvignon": "wine", "cabernet franc": "wine", "sauvignon blanc": "wine",
    "pinot grigio": "wine", "pinot gris": "wine", "pinot noir": "wine",
    "chenin blanc": "wine", "chardonnay": "wine", "merlot": "wine",
    "riesling": "wine", "zinfandel": "wine", "malbec": "wine", "syrah": "wine",
    "shiraz": "wine", "moscato": "wine", "viognier": "wine", "grenache": "wine",
    "tempranillo": "wine", "sangiovese": "wine", "nebbiolo": "wine",
    # Malt beverages.
    "beer": "malt beverage", "ale": "malt beverage", "lager": "malt beverage",
    "stout": "malt beverage", "porter": "malt beverage", "malt beverage": "malt beverage",
}

# Keywords that anchor the producer/bottler/importer line.
PRODUCER_KEYWORDS = [
    "PRODUCED BY", "PRODUCED AND BOTTLED BY", "DISTILLED BY", "DISTILLED AND BOTTLED BY",
    "BOTTLED BY", "BOTTLED AND CANNED BY", "CANNED BY", "PACKED BY", "IMPORTED BY",
    "VINTED BY", "BREWED BY",
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
