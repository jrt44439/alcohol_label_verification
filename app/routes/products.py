from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.documents import extract as document_extract
from app.documents import field_extractors as document_field_extractors
from app.models import product as product_model
from config import CANONICAL_WARNING

bp = Blueprint("products", __name__, url_prefix="/products")


def _form_to_data() -> dict:
    return {field: request.form.get(field, "").strip() or None for field in product_model.FIELD_NAMES}


def _extract_from_uploaded_document(data: dict) -> dict:
    """Merge fields extracted from an uploaded reference document into ``data``,
    keeping anything already typed for fields the document didn't yield."""
    doc_file = request.files.get("reference_document")
    if doc_file is None or doc_file.filename == "":
        flash("Choose a PDF or Word document to extract from.", "error")
        return data

    try:
        text = document_extract.extract_text(doc_file)
    except ValueError as e:
        flash(str(e), "error")
        return data

    if not text.strip():
        flash("No extractable text found in that document (it may be a scanned image) — enter fields manually.", "error")
        return data

    extracted = document_field_extractors.extract_all_fields_from_document(text)
    for field in product_model.DOCUMENT_FILLABLE_FIELDS:
        if extracted.get(field):
            data[field] = extracted[field]

    flash("Extracted fields from the document — review and correct anything below, then Save.", "success")
    return data


@bp.route("/")
def list_products():
    products = product_model.get_all()
    return render_template("products/list.html", products=products)


@bp.route("/new", methods=["GET", "POST"])
def new_product():
    if request.method == "POST":
        data = _form_to_data()
        action = request.form.get("action", "save")

        if action == "extract":
            data = _extract_from_uploaded_document(data)
            return render_template(
                "products/form.html", product=data, is_new=True, canonical_warning=CANONICAL_WARNING
            )

        if not data.get("name"):
            flash("Product name is required.", "error")
            return render_template(
                "products/form.html", product=data, is_new=True, canonical_warning=CANONICAL_WARNING
            )
        product_model.create(data)
        flash(f"Saved '{data['name']}' to the product library.", "success")
        return redirect(url_for("products.list_products"))

    default = {field: None for field in product_model.FIELD_NAMES}
    return render_template("products/form.html", product=default, is_new=True, canonical_warning=CANONICAL_WARNING)


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    existing = product_model.get_by_id(product_id)
    if existing is None:
        flash("Product not found.", "error")
        return redirect(url_for("products.list_products"))

    if request.method == "POST":
        data = _form_to_data()
        action = request.form.get("action", "save")

        if action == "extract":
            data = _extract_from_uploaded_document(data)
            return render_template(
                "products/form.html",
                product=data,
                is_new=False,
                product_id=product_id,
                canonical_warning=CANONICAL_WARNING,
            )

        if not data.get("name"):
            flash("Product name is required.", "error")
            return render_template(
                "products/form.html",
                product=data,
                is_new=False,
                product_id=product_id,
                canonical_warning=CANONICAL_WARNING,
            )
        product_model.update(product_id, data)
        flash(f"Updated '{data['name']}'.", "success")
        return redirect(url_for("products.list_products"))

    return render_template(
        "products/form.html", product=existing, is_new=False, product_id=product_id, canonical_warning=CANONICAL_WARNING
    )


@bp.route("/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    existing = product_model.get_by_id(product_id)
    if existing is not None:
        product_model.delete(product_id)
        flash(f"Deleted '{existing.name}'.", "success")
    return redirect(url_for("products.list_products"))
