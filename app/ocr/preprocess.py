"""Image loading and preprocessing to improve OCR accuracy."""
import cv2
import numpy as np
from PIL import Image, ImageOps

# Below this width, small print (e.g. the government-mandated fine print
# producer/address line) becomes too few pixels tall for Tesseract to
# resolve reliably, so we upscale before running OCR. Raised from the
# original 1800 -- even a photo that already clears that width can still
# leave the smallest label text under-resolved, since a bottle photo's
# overall resolution doesn't scale with how tiny its fine print is.
MIN_OCR_WIDTH = 2400


def load_image(file_storage) -> Image.Image:
    """Load an uploaded file into a PIL Image, correcting EXIF orientation."""
    image = Image.open(file_storage.stream)
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def to_cv2(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def grayscale(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def upscale(img: np.ndarray, min_width: int = MIN_OCR_WIDTH) -> np.ndarray:
    """Enlarge small/low-resolution photos so small print has enough pixel
    height for Tesseract to resolve; a no-op for already-large images."""
    height, width = img.shape[:2]
    if width >= min_width:
        return img
    scale = min_width / width
    return cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_CUBIC)


def denoise(img: np.ndarray) -> np.ndarray:
    # A lighter touch than a large filter strength -- aggressive denoising
    # blurs the thin strokes of small print and decorative fonts, which is
    # what causes adjacent letters to blur/merge together.
    return cv2.fastNlMeansDenoising(img, h=7)


def enhance_contrast(img: np.ndarray) -> np.ndarray:
    """Locally boost contrast (CLAHE) so faint/embossed small print and
    unusual fonts stand out from the background."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img)


def threshold(img: np.ndarray) -> np.ndarray:
    """Binarize with adaptive (local) thresholding. Not used in the default
    pipeline (see note in preprocess_pipeline) but kept available -- some
    very low-contrast or unevenly-lit photos still benefit from forcing a
    hard black/white split before OCR."""
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


def _skew_angle(img: np.ndarray) -> float:
    """Estimate the skew angle from a temporary binarization of ``img``,
    without altering the image itself."""
    binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(binary > 0))
    if coords.shape[0] < 50:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    return angle


def deskew(img: np.ndarray) -> np.ndarray:
    """Rotate the image to correct small skew angles based on text pixel
    contours, detected via a temporary internal binarization -- the returned
    image keeps ``img``'s own pixel values (e.g. grayscale), just rotated."""
    angle = _skew_angle(img)
    if abs(angle) < 0.5:
        return img
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess_pipeline(image: Image.Image) -> np.ndarray:
    """Run the full preprocessing pipeline, returning an image ready for Tesseract.

    Deliberately does NOT hard-binarize the final image. Tesseract's LSTM
    recognizer was trained on, and does its own internal binarization tuned
    for, near-original grayscale images -- an externally applied fixed-size
    adaptive threshold tends to fuse touching letters or fragment thin
    strokes depending on how the block size lines up with the actual font,
    which shows up as combined/misread letters. We instead hand Tesseract a
    clean, upscaled, denoised, contrast-enhanced, deskewed grayscale image
    and let it binarize internally.
    """
    img = to_cv2(image)
    img = grayscale(img)
    img = upscale(img)
    img = denoise(img)
    img = enhance_contrast(img)
    img = deskew(img)
    return img
