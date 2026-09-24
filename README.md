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

## Standalone Windows build

Packages the app into a double-clickable `.exe` (with a bundled copy of
Tesseract) that opens itself in the default browser -- no separate Python
or Tesseract install needed on the machine that runs it.

1. Make sure your own dev setup above is working first (Tesseract
   installed, `requirements.txt` installed into `.venv`).
2. Install the build-only dependency:
   ```
   pip install -r requirements-build.txt
   ```
3. Stage a trimmed copy of your local Tesseract install (binary + DLLs +
   the English trained-data file) into `packaging/tesseract/`:
   ```
   python packaging/stage_tesseract.py
   ```
   Re-run this after updating Tesseract, before rebuilding.
4. Build:
   ```
   pyinstaller desktop_app.spec
   ```
   Output is a folder at `dist/AlcoholLabelVerification/` --
   `AlcoholLabelVerification.exe` (using the icon at
   `packaging/label_verifier.ico`) plus everything it needs alongside it.
   A console window stays open while it runs -- closing it stops the app.
5. Sign it:
   ```
   powershell -ExecutionPolicy Bypass -File packaging/sign_exe.ps1
   ```
   The first run generates a self-signed code-signing certificate (saved
   under `packaging/codesign/`, gitignored -- machine-local, never checked
   in) and reuses that same certificate on every later build, so each
   release carries a consistent publisher identity. See the limitation
   below before relying on this for distribution.
   Zip the whole `dist/AlcoholLabelVerification/` folder to hand it to
   someone else; double-clicking the `.exe` starts a local server and
   opens the app in their default browser.

Notes:
- The database and any temporarily-uploaded photos live in
  `%LOCALAPPDATA%\AlcoholLabelVerification\`, not inside the app folder
  itself, so they persist across rebuilds/reinstalls and the bundle itself
  can stay read-only.
- `desktop_app.py` is the packaged entry point (runs on `waitress`, a
  production WSGI server, and auto-opens the browser) -- it's separate
  from `wsgi.py`, which is still what `flask run` uses for normal
  development.
- **Code-signing limitation:** the self-signed certificate `sign_exe.ps1`
  generates proves the exe hasn't been altered since signing and gives it
  a consistent identity across builds, but it does **not** stop Windows
  SmartScreen's "Windows protected your PC" warning on a machine that
  hasn't explicitly been told to trust this specific certificate --
  self-signing can't do that for machines you don't control. On a
  machine you *do* control, import `packaging/codesign/AlcoholLabelVerification.cer`
  into its Trusted Root Certification Authorities store once, and the
  warning stops appearing there. To avoid the warning everywhere,
  including machines you've never touched, you need a certificate from a
  recognized certificate authority (an OV or EV code-signing certificate,
  e.g. from DigiCert, Sectigo, or SSL.com -- typically $70-400+/year and
  requires identity verification); once you have that `.pfx`, swap it in
  for the one `sign_exe.ps1` generates.

## Server deployment (Docker)

A `Dockerfile` packages the app as a normal, always-running server process
(installing Tesseract OCR via `apt` -- no cloud OCR API involved) for a
host that supports it, rather than a serverless one. `server.py` is the
container's entry point: it serves the app on all interfaces via
`waitress` and reads `PORT` from the environment. This setup hasn't been
build-tested locally (no Docker available in the environment that wrote
it) -- both platforms below build it remotely, so watch the first
deploy's build log for any apt/pip error and adjust the `Dockerfile`
accordingly if one shows up.

The database and any uploaded-photo temp files need to live on a
**persistent volume/disk** mounted at `/data` (both configs below set this
up) -- without one, they're wiped on every redeploy, since a container's
own filesystem doesn't persist.

### Fly.io (recommended -- persistent volumes are straightforward and cheap)

```
flyctl auth login          # opens a browser to sign in / create an account
flyctl launch --no-deploy  # picks up fly.toml; choose a unique app name if prompted
flyctl volumes create data --region iad --size 1
flyctl deploy
```

`fly.toml` is already set up with a `[mounts]` section pointing at that
volume, and `auto_stop_machines`/`min_machines_running = 0` so it doesn't
cost anything while idle (at the cost of a few seconds' cold start on the
next request -- set `min_machines_running = 1` if you'd rather avoid
that).

### Render (alternative -- note the free-tier caveat)

Connect the GitHub repo on [render.com](https://render.com) and it picks
up `render.yaml` automatically (or `New +` -> `Blueprint`). **Render's
free tier has no persistent disk** -- `render.yaml` requests one, which
requires at least the "starter" paid plan; on free tier, the product
library and saved COLA results would be wiped on every redeploy.

### Either way

- Uploaded label photos are still never sent anywhere outside the
  container itself -- Tesseract runs locally inside it, same as the
  desktop/dev versions.
- `MAX_CONTENT_LENGTH` (60 MB, see `config.py`) caps upload size; both
  platforms' own request-size limits may be smaller by default depending
  on plan.

## Using the app

1. Go to **Product Library** and add the reference values for a product you
   want to verify (brand, class/type, ABV, net contents, producer, country of
   origin). You can type these in by hand, or upload a PDF/Word reference
   document (e.g. a spec sheet) and click **Extract from Document** to prefill
   the fields — review and correct before saving. The Government Health
   Warning is not stored per product: it's federally standardized wording, so
   every verification always checks against the one fixed, correct text.
2. Go to **Verify Labels** and select one or more label photos. By default
   each photo is automatically matched against your product library — or
   switch the batch to compare against a single uploaded **COLA application**
   (PDF/Word) instead, extracting its stated fields once and checking every
   photo in the batch against them (any label photos already embedded in the
   document are pulled out automatically). You can also override auto-match
   per photo to pick a specific saved product or type values in ad hoc.
3. The comparison runs immediately. Photos sharing the same reference (e.g.
   front + back photos of one product) are grouped into a single summary
   table — one row per field, showing whether it was found correctly
   *somewhere* in that set of photos, who found it, and what was expected.
   Below the table, each photo has its own collapsed card with the raw OCR
   text and editable fields; expand one to correct a misread field and
   re-run the comparison, which updates the summary table too.
4. From an expanded card you can also **Update Matched Product** (overwrite
   that saved product with the corrected values) or **Save as New Product**
   (add these values as a new library entry) — useful for COLA-sourced or
   unmatched results too.
5. To check and keep a record of several COLA applications at once, pick
   **"A batch of COLA applications"** on the Verify Labels page. Each
   document is processed independently and the result is **saved
   automatically** — no review step first. Photos themselves are never
   saved, only the extracted values, match status, and raw OCR text. Review
   everything afterward (and correct any misread field, which persists) from
   **Saved Results**.

## Notes

- Only the product library and saved COLA batch results persist. A live
  (non-batch) verify run is otherwise ephemeral — nothing about it is kept
  once you navigate away, other than what you explicitly save via Update/Save
  Product. Uploaded images are written temporarily to `uploads/` to display
  alongside a live run's results; that folder is gitignored and can be
  cleared manually. Saved batch results never write any image to disk.
- Brand name extraction relies on a best-effort heuristic (the largest text
  block on the label) and is the field most likely to need manual correction.
- Reference document extraction (product library or COLA application) only
  reads text directly embedded in the PDF or Word file; a scanned/photographed
  document with no extractable text layer isn't supported — enter fields
  manually in that case.
- Alcohol content and net contents are always required to be *on the label
  photo itself* — even if a reference source (a COLA application, or a saved
  product) doesn't state them, a photo missing either is flagged NOT FOUND.
  Country of origin stays conditional (blank reference + blank label is fine,
  since it's only required for imports).
- The Government Warning is checked three ways: its text against the fixed
  27 CFR 16.21 wording, whether the "GOVERNMENT WARNING" heading is in all
  capital letters, and (best-effort, image-based) whether that heading is
  bold — the bold check can misfire on noisy or angled photos, so treat it as
  a hint to verify visually rather than a certainty.
- OCR image preprocessing (upscaling, denoising, contrast enhancement) hands
  Tesseract a clean grayscale image rather than a hard black/white threshold —
  deliberately, since pre-binarizing tends to fuse or fragment letters more
  than it helps. Tesseract's page-segmentation mode is tuned for a typical
  single-column bottle label with mixed font sizes. If a particular label
  layout still reads poorly, try setting the `TESSERACT_CONFIG` environment
  variable to a different mode, e.g. `--oem 3 --psm 11` (sparse text, for
  labels with text scattered in unrelated blocks) or `--oem 3 --psm 6` (a
  single uniform block of text).
