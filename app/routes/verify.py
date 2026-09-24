import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app.comparison import compare as compare_module
from app.documents import extract as document_extract
from app.documents import field_extractors as document_field_extractors
from app.models import product as product_model
from app.models import verification as verification_model
from app.ocr import engine, field_extractors, preprocess, warning_format
from config import CANONICAL_WARNING

bp = Blueprint("verify", __name__, url_prefix="/verify")


def _find_best_matching_product(extracted: dict) -> tuple[int | None, int]:
    """Scan the whole product library for the best match to extracted label
    fields. Returns (product_id_or_None, matched_count_out_of_6)."""
    cfg = current_app.config
    candidates = [
        {"id": p.id, **{f: getattr(p, f) for f in product_model.DOCUMENT_FILLABLE_FIELDS}}
        for p in product_model.get_all()
    ]
    return compare_module.find_best_match(
        extracted,
        candidates,
        text_threshold=cfg["TEXT_MATCH_THRESHOLD"],
        abv_tolerance=cfg["ABV_TOLERANCE_PCT"],
        volume_tolerance_pct=cfg["VOLUME_TOLERANCE_PCT"],
    )


def _extract_cola_expected(doc_file) -> tuple[dict | None, str | None]:
    """Extract the 6 reference fields once from an uploaded COLA application,
    for use as every photo's expected values. Returns (expected, None) on
    success or (None, error_message) if the document text can't be read --
    the caller decides how to present the error (a single-document upload
    flashes it as-is; a batch prefixes it with the filename)."""
    try:
        text = document_extract.extract_text(doc_file)
    except ValueError as e:
        return None, str(e)

    if not text.strip():
        return None, (
            "No extractable text found in that COLA application (it may be a scanned image) — "
            "enter values manually or use a saved product instead."
        )

    extracted = document_field_extractors.extract_all_fields_from_document(text)
    expected = {f: extracted.get(f) for f in product_model.DOCUMENT_FILLABLE_FIELDS}
    expected["health_warning_text"] = CANONICAL_WARNING
    return expected, None


def _serialize_comparison(comp) -> dict:
    return {
        "status": comp.status.value,
        "extracted_value": comp.extracted_value,
        "expected_value": comp.expected_value,
        "score": comp.score,
    }


def _process_cola_document_for_save(doc_file) -> tuple[dict | None, str | None]:
    """Run the full COLA pipeline for one document -- text fields plus every
    embedded label photo, OCR'd and compared -- with no image files written
    to disk. Returns (result, None) on success, where result is ready for
    app.models.verification.create()/update(), or (None, error_message)."""
    expected, error = _extract_cola_expected(doc_file)
    if expected is None:
        return None, error

    embedded_images = document_extract.extract_images(doc_file)

    engine.configure_tesseract(current_app.config.get("TESSERACT_CMD"))
    min_confidence = current_app.config["OCR_MIN_CONFIDENCE"]
    tesseract_config = current_app.config["TESSERACT_CONFIG"]

    live_items = []
    for i, image in enumerate(embedded_images):
        preprocessed = preprocess.preprocess_pipeline(image)
        ocr_result = engine.run_ocr(preprocessed, min_confidence=min_confidence, config=tesseract_config)
        extracted = field_extractors.extract_all_fields(ocr_result)
        live_items.append(
            {
                "index": i,
                "raw_text": ocr_result.raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": _compare(extracted, expected, allow_broad_class_type=True),
                "warning_caps_ok": warning_format.check_heading_all_caps(ocr_result.raw_text),
                "warning_bold_ok": warning_format.detect_heading_bold(preprocessed, ocr_result),
            }
        )

    if live_items:
        cfg = current_app.config
        field_summary = {
            field: compare_module.aggregate_field(
                field,
                live_items,
                text_threshold=cfg["TEXT_MATCH_THRESHOLD"],
                warning_threshold=cfg["WARNING_MATCH_THRESHOLD"],
                abv_tolerance=cfg["ABV_TOLERANCE_PCT"],
                volume_tolerance_pct=cfg["VOLUME_TOLERANCE_PCT"],
            )
            for field in product_model.LABEL_FIELDS
        }
    else:
        # No embedded photos found at all -- nothing to check the application
        # against, but still record what it claimed.
        field_summary = {field: {"status": "not_found", "expected": expected.get(field)} for field in product_model.LABEL_FIELDS}

    photos = [
        {
            "index": it["index"],
            "raw_text": it["raw_text"],
            "extracted": it["extracted"],
            "expected": it["expected"],
            "comparisons_by_field": {k: _serialize_comparison(v) for k, v in it["comparisons_by_field"].items()},
            "warning_caps_ok": it["warning_caps_ok"],
            "warning_bold_ok": it["warning_bold_ok"],
        }
        for it in live_items
    ]

    return {
        "field_summary": field_summary,
        "warning_caps_ok": _aggregate_tristate(live_items, "warning_caps_ok") if live_items else None,
        "warning_bold_ok": _aggregate_tristate(live_items, "warning_bold_ok") if live_items else None,
        "photos": photos,
    }, None


def _build_expected(index: int, extracted: dict) -> tuple[dict, str | None, int | None, str]:
    """Build the expected-values dict for photo ``index``, from auto-matching
    against the product library, a manually selected product, or that row's
    ad hoc fields. Returns (expected, product_name, matched_product_id, reference_mode)."""
    reference_mode = request.form.get(f"reference_mode_{index}", "auto")
    product_name = None
    matched_product_id = None

    if reference_mode == "auto":
        best_id, _ = _find_best_matching_product(extracted)
        product = product_model.get_by_id(best_id) if best_id else None
        if product is not None:
            expected = {f: getattr(product, f) for f in product_model.DOCUMENT_FILLABLE_FIELDS}
            product_name = product.name
            matched_product_id = product.id
        else:
            expected = {f: None for f in product_model.DOCUMENT_FILLABLE_FIELDS}
    elif reference_mode == "product":
        product_id = request.form.get(f"product_id_{index}")
        product = product_model.get_by_id(int(product_id)) if product_id else None
        if product is not None:
            expected = {f: getattr(product, f) for f in product_model.DOCUMENT_FILLABLE_FIELDS}
            product_name = product.name
            matched_product_id = product.id
        else:
            expected = {f: None for f in product_model.DOCUMENT_FILLABLE_FIELDS}
    else:  # "adhoc"
        expected = {
            f: request.form.get(f"expected_{f}_{index}", "").strip() or None
            for f in product_model.DOCUMENT_FILLABLE_FIELDS
        }

    expected["health_warning_text"] = CANONICAL_WARNING
    return expected, product_name, matched_product_id, reference_mode


def _compare(extracted: dict, expected: dict, allow_broad_class_type: bool = False) -> dict:
    cfg = current_app.config
    comparisons = compare_module.compare_product(
        extracted,
        expected,
        text_threshold=cfg["TEXT_MATCH_THRESHOLD"],
        warning_threshold=cfg["WARNING_MATCH_THRESHOLD"],
        abv_tolerance=cfg["ABV_TOLERANCE_PCT"],
        volume_tolerance_pct=cfg["VOLUME_TOLERANCE_PCT"],
        allow_broad_class_type=allow_broad_class_type,
    )
    return {c.field_key: c for c in comparisons}


def _matched_count(comparisons_by_field: dict) -> int:
    return sum(
        1
        for f in product_model.DOCUMENT_FILLABLE_FIELDS
        if comparisons_by_field[f].status == compare_module.MatchStatus.MATCH
    )


def _match_kind(reference_mode: str, matched_product_id: int | None, matched_count: int) -> str | None:
    """None means "no product-match banner" (ad hoc / COLA-sourced entries
    just show the per-field badges). Otherwise "exact", "partial", or "none"."""
    if reference_mode in ("adhoc", "cola"):
        return None
    if matched_product_id is not None:
        return "exact" if matched_count == len(product_model.DOCUMENT_FILLABLE_FIELDS) else "partial"
    return "none"


def _encode_tristate(value: bool | None) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return ""


def _decode_tristate(value: str | None) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _aggregate_tristate(items: list[dict], key: str) -> bool | None:
    values = [it[key] for it in items]
    if any(v is True for v in values):
        return True
    if any(v is False for v in values):
        return False
    return None


def _group_key(item: dict) -> tuple:
    """Identity used to group photos that share the same reference, so the
    summary table aggregates fields across, say, front+back photos of one
    product -- without silently merging a batch of genuinely different
    products into one misleading table."""
    if item["matched_product_id"] is not None:
        return ("product", item["matched_product_id"])
    if item["reference_mode"] == "cola":
        return ("cola",)
    return ("standalone", item["index"])


def _group_items(items: list[dict]) -> list[dict]:
    """Group items by reference identity and compute a per-field aggregate
    summary for each group (see compare_module.aggregate_field)."""
    cfg = current_app.config
    order = []
    grouped = {}
    for item in items:
        key = _group_key(item)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(item)

    groups = []
    for key in order:
        group_items = grouped[key]
        if key[0] == "product":
            label = group_items[0]["product_name"] or "Saved Product"
        elif key[0] == "cola":
            label = "COLA Application"
        else:
            label = f"Label {group_items[0]['index'] + 1}"

        field_summary = {
            field: compare_module.aggregate_field(
                field,
                group_items,
                text_threshold=cfg["TEXT_MATCH_THRESHOLD"],
                warning_threshold=cfg["WARNING_MATCH_THRESHOLD"],
                abv_tolerance=cfg["ABV_TOLERANCE_PCT"],
                volume_tolerance_pct=cfg["VOLUME_TOLERANCE_PCT"],
            )
            for field in product_model.LABEL_FIELDS
        }

        groups.append(
            {
                "label": label,
                "photos": group_items,
                "field_summary": field_summary,
                "warning_caps_ok": _aggregate_tristate(group_items, "warning_caps_ok"),
                "warning_bold_ok": _aggregate_tristate(group_items, "warning_bold_ok"),
            }
        )
    return groups


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
    batch_reference_mode = request.form.get("batch_reference_mode", "auto")
    uploaded_files = [f for f in request.files.getlist("label_images") if f and f.filename]

    shared_expected = None
    embedded_images = []
    if batch_reference_mode == "cola":
        cola_file = request.files.get("cola_document")
        if cola_file is None or cola_file.filename == "":
            flash("Please choose a COLA application PDF or Word document.", "error")
            return redirect(url_for("verify.upload"))

        shared_expected, error = _extract_cola_expected(cola_file)
        if shared_expected is None:
            flash(error, "error")
            return redirect(url_for("verify.upload"))

        # Label photos already attached to the application don't need to be
        # re-uploaded separately -- pull them out automatically.
        embedded_images = document_extract.extract_images(cola_file)

    # Unify manually uploaded photos and any images pulled from the COLA
    # application into one (PIL image, display filename) list to process.
    image_sources = [(preprocess.load_image(f), f.filename) for f in uploaded_files]
    image_sources += [
        (img, f"cola_application_image_{n}.png") for n, img in enumerate(embedded_images, start=1)
    ]

    if not image_sources:
        if batch_reference_mode == "cola":
            flash(
                "No label photos found — the COLA application didn't contain any embedded "
                "images, and none were uploaded manually.",
                "error",
            )
        else:
            flash("Please choose at least one label photo to upload.", "error")
        return redirect(url_for("verify.upload"))

    engine.configure_tesseract(current_app.config.get("TESSERACT_CMD"))
    min_confidence = current_app.config["OCR_MIN_CONFIDENCE"]
    tesseract_config = current_app.config["TESSERACT_CONFIG"]
    upload_folder = current_app.config["UPLOAD_FOLDER"]

    items = []
    for i, (image, display_filename) in enumerate(image_sources):
        preprocessed = preprocess.preprocess_pipeline(image)
        ocr_result = engine.run_ocr(preprocessed, min_confidence=min_confidence, config=tesseract_config)
        extracted = field_extractors.extract_all_fields(ocr_result)

        warning_caps_ok = warning_format.check_heading_all_caps(ocr_result.raw_text)
        warning_bold_ok = warning_format.detect_heading_bold(preprocessed, ocr_result)

        if batch_reference_mode == "cola":
            expected = dict(shared_expected)
            product_name = None
            matched_product_id = None
            reference_mode = "cola"
        else:
            expected, product_name, matched_product_id, reference_mode = _build_expected(i, extracted)

        filename = f"{uuid.uuid4().hex}_{secure_filename(display_filename)}"
        image.save(os.path.join(upload_folder, filename))

        comparisons_by_field = _compare(extracted, expected, allow_broad_class_type=(reference_mode == "cola"))
        matched_count = _matched_count(comparisons_by_field)

        items.append(
            {
                "index": i,
                "image_filename": filename,
                "product_name": product_name,
                "matched_product_id": matched_product_id,
                "reference_mode": reference_mode,
                "raw_text": ocr_result.raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": comparisons_by_field,
                "matched_count": matched_count,
                "match_kind": _match_kind(reference_mode, matched_product_id, matched_count),
                "warning_caps_ok": warning_caps_ok,
                "warning_bold_ok": warning_bold_ok,
            }
        )

    return render_template(
        "verify/results.html",
        stage="review",
        groups=_group_items(items),
        item_count=len(items),
        label_fields=product_model.LABEL_FIELDS,
        field_display_names=compare_module.FIELD_DISPLAY_NAMES,
        reference_field_count=len(product_model.DOCUMENT_FILLABLE_FIELDS),
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
        matched_product_id_raw = request.form.get(f"matched_product_id_{i}") or None
        matched_product_id = int(matched_product_id_raw) if matched_product_id_raw else None
        reference_mode = request.form.get(f"reference_mode_{i}", "adhoc")
        warning_caps_ok = _decode_tristate(request.form.get(f"warning_caps_ok_{i}"))
        warning_bold_ok = _decode_tristate(request.form.get(f"warning_bold_ok_{i}"))

        comparisons_by_field = _compare(extracted, expected, allow_broad_class_type=(reference_mode == "cola"))
        matched_count = _matched_count(comparisons_by_field)

        items.append(
            {
                "index": i,
                "image_filename": image_filename,
                "product_name": product_name,
                "matched_product_id": matched_product_id,
                "reference_mode": reference_mode,
                "raw_text": raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": comparisons_by_field,
                "matched_count": matched_count,
                "match_kind": _match_kind(reference_mode, matched_product_id, matched_count),
                "warning_caps_ok": warning_caps_ok,
                "warning_bold_ok": warning_bold_ok,
            }
        )

    return render_template(
        "verify/results.html",
        stage="compared",
        groups=_group_items(items),
        item_count=len(items),
        label_fields=product_model.LABEL_FIELDS,
        field_display_names=compare_module.FIELD_DISPLAY_NAMES,
        reference_field_count=len(product_model.DOCUMENT_FILLABLE_FIELDS),
    )


@bp.route("/save-product", methods=["POST"])
def save_product():
    action = request.form.get("action")
    data = {f: request.form.get(f, "").strip() or None for f in product_model.DOCUMENT_FILLABLE_FIELDS}

    if action == "update":
        product_id = request.form.get("product_id")
        existing = product_model.get_by_id(int(product_id)) if product_id else None
        if existing is None:
            flash("Product not found.", "error")
            return redirect(url_for("verify.upload"))
        data["name"] = existing.name
        product_model.update(existing.id, data)
        flash(f"Updated '{existing.name}' with the corrected values.", "success")
    else:
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Enter a name for the new product before saving.", "error")
            return redirect(url_for("verify.upload"))
        data["name"] = name
        product_model.create(data)
        flash(f"Saved '{name}' to the product library.", "success")

    return redirect(url_for("products.list_products"))


@bp.route("/run-cola-batch", methods=["POST"])
def run_cola_batch():
    doc_files = [f for f in request.files.getlist("cola_documents") if f and f.filename]
    if not doc_files:
        flash("Please choose at least one COLA application PDF or Word document.", "error")
        return redirect(url_for("verify.upload"))

    saved_count = 0
    for doc_file in doc_files:
        result, error = _process_cola_document_for_save(doc_file)
        if result is None:
            flash(f"{doc_file.filename}: {error}", "error")
            continue
        verification_model.create(
            doc_file.filename,
            result["field_summary"],
            result["warning_caps_ok"],
            result["warning_bold_ok"],
            result["photos"],
        )
        saved_count += 1

    if saved_count:
        flash(f"Saved {saved_count} verification result{'s' if saved_count != 1 else ''}.", "success")
    return redirect(url_for("verify.list_saved_results"))


@bp.route("/results")
def list_saved_results():
    verifications = verification_model.get_all()
    return render_template("verify/saved_list.html", verifications=verifications)


@bp.route("/results/<int:verification_id>")
def view_saved_result(verification_id):
    verification = verification_model.get_by_id(verification_id)
    if verification is None:
        flash("Saved verification not found.", "error")
        return redirect(url_for("verify.list_saved_results"))
    return render_template(
        "verify/saved_detail.html",
        verification=verification,
        label_fields=product_model.LABEL_FIELDS,
        field_display_names=compare_module.FIELD_DISPLAY_NAMES,
    )


@bp.route("/results/<int:verification_id>/update", methods=["POST"])
def update_saved_result(verification_id):
    verification = verification_model.get_by_id(verification_id)
    if verification is None:
        flash("Saved verification not found.", "error")
        return redirect(url_for("verify.list_saved_results"))

    photo_count = len(verification.photos)
    live_items = []
    photos = []
    for i in range(photo_count):
        extracted = {f: request.form.get(f"extracted_{f}_{i}", "").strip() or None for f in product_model.LABEL_FIELDS}
        expected = {f: request.form.get(f"expected_{f}_{i}", "").strip() or None for f in product_model.LABEL_FIELDS}
        raw_text = request.form.get(f"raw_text_{i}", "")
        warning_caps_ok = _decode_tristate(request.form.get(f"warning_caps_ok_{i}"))
        warning_bold_ok = _decode_tristate(request.form.get(f"warning_bold_ok_{i}"))

        comparisons_by_field = _compare(extracted, expected, allow_broad_class_type=True)
        live_items.append(
            {
                "index": i,
                "raw_text": raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": comparisons_by_field,
                "warning_caps_ok": warning_caps_ok,
                "warning_bold_ok": warning_bold_ok,
            }
        )
        photos.append(
            {
                "index": i,
                "raw_text": raw_text,
                "extracted": extracted,
                "expected": expected,
                "comparisons_by_field": {k: _serialize_comparison(v) for k, v in comparisons_by_field.items()},
                "warning_caps_ok": warning_caps_ok,
                "warning_bold_ok": warning_bold_ok,
            }
        )

    if live_items:
        cfg = current_app.config
        field_summary = {
            field: compare_module.aggregate_field(
                field,
                live_items,
                text_threshold=cfg["TEXT_MATCH_THRESHOLD"],
                warning_threshold=cfg["WARNING_MATCH_THRESHOLD"],
                abv_tolerance=cfg["ABV_TOLERANCE_PCT"],
                volume_tolerance_pct=cfg["VOLUME_TOLERANCE_PCT"],
            )
            for field in product_model.LABEL_FIELDS
        }
        warning_caps_ok = _aggregate_tristate(live_items, "warning_caps_ok")
        warning_bold_ok = _aggregate_tristate(live_items, "warning_bold_ok")
    else:
        field_summary = verification.field_summary
        warning_caps_ok = verification.warning_caps_ok
        warning_bold_ok = verification.warning_bold_ok

    verification_model.update(verification_id, field_summary, warning_caps_ok, warning_bold_ok, photos)
    flash("Saved corrections.", "success")
    return redirect(url_for("verify.view_saved_result", verification_id=verification_id))


@bp.route("/results/<int:verification_id>/delete", methods=["POST"])
def delete_saved_result(verification_id):
    verification_model.delete(verification_id)
    flash("Deleted saved verification.", "success")
    return redirect(url_for("verify.list_saved_results"))


@bp.route("/image/<path:filename>")
def image(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
