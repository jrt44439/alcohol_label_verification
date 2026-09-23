import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app.comparison import compare as compare_module
from app.models import product as product_model
from app.ocr import engine, field_extractors, preprocess
from config import CANONICAL_WARNING

bp = Blueprint("verify", __name__, url_prefix="/verify")


def _build_expected(index: int) -> tuple[dict, str | None]:
    """Build the expected-values dict for photo ``index`` from either a
    selected saved product or that row's ad hoc fields, returning
    (expected, product_name)."""
    reference_mode = request.form.get(f"reference_mode_{index}", "product")
    product_name = None

    if reference_mode == "product":
        product_id = request.form.get(f"product_id_{index}")
        product = product_model.get_by_id(int(product_id)) if product_id else None
        if product is not None:
            expected = {f: getattr(product, f) for f in product_model.DOCUMENT_FILLABLE_FIELDS}
            product_name = product.name
        else:
            expected = {f: None for f in product_model.DOCUMENT_FILLABLE_FIELDS}
    else:
        expected = {
            f: request.form.get(f"expected_{f}_{index}", "").strip() or None
            for f in product_model.DOCUMENT_FILLABLE_FIELDS
        }

    expected["health_warning_text"] = CANONICAL_WARNING
    return expected, product_name


def _compare(extracted: dict, expected: dict) -> dict:
    cfg = current_app.config
    comparisons = compare_module.compare_product(
        extracted,
        expected,
        text_threshold=cfg["TEXT_MATCH_THRESHOLD"],
        warning_threshold=cfg["WARNING_MATCH_THRESHOLD"],
        abv_tolerance=cfg["ABV_TOLERANCE_PCT"],
        volume_tolerance_pct=cfg["VOLUME_TOLERANCE_PCT"],
    )
    return {c.field_key: c for c in comparisons}


@bp.route("/")
def upload():
    products = product_model.get_all()
    products_for_js = [{"id": p.id, "name": p.name} for p in products]
    return render_template(
        "verify/upload.html",
        products=products,
        products_for_js=products_for_js,
        label_fields=product_model.LABEL_FIELDS,
    )


@bp.route("/run", methods=["POST"])
def run():
    files = [f for f in request.files.getlist("label_images") if f and f.filename]
    if not files:
        flash("Please choose at least one label photo to upload.", "error")
        return redirect(url_for("verify.upload"))

    engine.configure_tesseract(current_app.config.get("TESSERACT_CMD"))
    min_confidence = current_app.config["OCR_MIN_CONFIDENCE"]
    tesseract_config = current_app.config["TESSERACT_CONFIG"]
    upload_folder = current_app.config["UPLOAD_FOLDER"]

    items = []
    for i, file in enumerate(files):
        image = preprocess.load_image(file)
        preprocessed = preprocess.preprocess_pipeline(image)
        ocr_result = engine.run_ocr(preprocessed, min_confidence=min_confidence, config=tesseract_config)
        extracted = field_extractors.extract_all_fields(ocr_result)

        expected, product_name = _build_expected(i)

        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        image.save(os.path.join(upload_folder, filename))

        items.append(
            {
                "index": i,
                "image_filename": filename,
                "product_name": product_name,
                "raw_text": ocr_result.raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": _compare(extracted, expected),
            }
        )

    return render_template(
        "verify/results.html",
        stage="review",
        items=items,
        label_fields=product_model.LABEL_FIELDS,
        field_display_names=compare_module.FIELD_DISPLAY_NAMES,
    )


@bp.route("/compare", methods=["POST"])
def compare():
    item_count = int(request.form.get("item_count", "0") or "0")

    items = []
    for i in range(item_count):
        extracted = {
            f: request.form.get(f"extracted_{f}_{i}", "").strip() or None for f in product_model.LABEL_FIELDS
        }
        expected = {
            f: request.form.get(f"expected_{f}_{i}", "").strip() or None for f in product_model.LABEL_FIELDS
        }
        raw_text = request.form.get(f"raw_text_{i}", "")
        image_filename = request.form.get(f"image_filename_{i}") or None
        product_name = request.form.get(f"product_name_{i}") or None

        items.append(
            {
                "index": i,
                "image_filename": image_filename,
                "product_name": product_name,
                "raw_text": raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": _compare(extracted, expected),
            }
        )

    return render_template(
        "verify/results.html",
        stage="compared",
        items=items,
        label_fields=product_model.LABEL_FIELDS,
        field_display_names=compare_module.FIELD_DISPLAY_NAMES,
    )


@bp.route("/image/<path:filename>")
def image(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
