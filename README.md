# Alcohol Label Verification

A local web app for checking a photographed alcohol bottle label against a set
of known-correct reference values: brand name, class/type, alcohol content,
net contents, producer/bottler/importer, country of origin, and the U.S.
Government Health Warning.

OCR runs entirely locally via Tesseract — no images or label data are sent to
any external service. Because local OCR and field-detection heuristics won't
always be perfect, the app shows you the raw OCR text and lets you review and
correct each extracted field before running the comparison.

## Setup

1. **Install the Tesseract OCR binary** (a separate program, not a Python
   package):
   - Windows: install via the [UB-Mannheim Tesseract installer](https://github.com/UB-Mannheim/tesseract/wiki)
     (or `choco install tesseract`). Note the install path, typically
     `C:\Program Files\Tesseract-OCR\tesseract.exe`.
   - If it's not on your `PATH`, set the `TESSERACT_CMD` environment variable
     to the full path of `tesseract.exe` before running the app.

2. **Create a virtual environment and install Python dependencies:**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Initialize the database:**
   ```
   flask --app wsgi init-db
   ```

4. **Run the dev server:**
   ```
   flask --app wsgi run --debug
   ```
   Then open `http://127.0.0.1:5000` in your browser.

5. **Run the test suite:**
   ```
   pytest
   ```

## Using the app

1. Go to **Product Library** and add the reference values for a product you
   want to verify (brand, class/type, ABV, net contents, producer, country of
   origin). You can type these in by hand, or upload a PDF/Word reference
   document (e.g. a spec sheet) and click **Extract from Document** to prefill
   the fields — review and correct before saving. The Government Health
   Warning is not stored per product: it's federally standardized wording, so
   every verification always checks against the one fixed, correct text.
2. Go to **Verify Labels** and select one or more label photos. For each
   photo, choose either a saved product or enter expected values for that
   photo now — a batch can mix different products in one upload.
3. Review the fields extracted from each photo (shown alongside its raw OCR
   text) and correct anything the app got wrong.
4. Run the comparison to see a per-field MATCH / MISMATCH / NOT FOUND result
   for every photo in the batch.

## Notes

- No verification history is saved — only the product library persists.
  Uploaded images are written temporarily to `uploads/` to display alongside
  results; that folder is gitignored and can be cleared manually.
- Brand name extraction relies on a best-effort heuristic (the largest text
  block on the label) and is the field most likely to need manual correction.
- Reference document extraction only reads text directly embedded in the PDF
  or Word file; a scanned/photographed document with no extractable text
  layer isn't supported — enter fields manually in that case.
- OCR image preprocessing (upscaling, contrast enhancement, adaptive
  thresholding) and Tesseract's page-segmentation mode are tuned for a
  typical single-column bottle label with mixed font sizes. If a particular
  label layout still reads poorly, try setting the `TESSERACT_CONFIG`
  environment variable to a different mode, e.g. `--oem 3 --psm 11` (sparse
  text, for labels with text scattered in unrelated blocks) or `--oem 3
  --psm 6` (a single uniform block of text).
