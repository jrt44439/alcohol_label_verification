"""Build-time helper for the standalone Windows build: copies the files a
bundled build needs from a local Tesseract OCR install into
packaging/tesseract/, trimmed to just the runtime binary, its DLLs, and the
English + orientation-detection trained-data files -- skipping the training
tools, docs, and other languages that ship with a full Tesseract install
but aren't needed to run OCR.

Run this once before building with PyInstaller:

    python packaging/stage_tesseract.py
    pyinstaller desktop_app.spec

Re-run it any time your local Tesseract install is updated, before
rebuilding. The staged packaging/tesseract/ folder is gitignored -- it's
regenerated from your local install, not checked in.
"""
import os
import shutil

DEST = os.path.join(os.path.dirname(__file__), "tesseract")

# Just what's needed for the OCR modes this app actually uses (--oem 3
# --psm 4 by default, configurable via TESSERACT_CONFIG) -- eng for text
# recognition, osd for orientation/script detection if a PSM mode needs it.
TESSDATA_FILES = ("eng.traineddata", "osd.traineddata")

DEFAULT_INSTALL_DIR = r"C:\Program Files\Tesseract-OCR"


def _find_source_dir() -> str:
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd and os.path.isfile(cmd):
        return os.path.dirname(cmd)
    if os.path.isfile(os.path.join(DEFAULT_INSTALL_DIR, "tesseract.exe")):
        return DEFAULT_INSTALL_DIR
    found = shutil.which("tesseract")
    if found:
        return os.path.dirname(found)
    raise SystemExit(
        "Could not find a local Tesseract install to stage from. Install "
        "Tesseract OCR first (see README.md), or set the TESSERACT_CMD "
        "environment variable to your tesseract.exe path and re-run this "
        "script."
    )


def main() -> None:
    source = _find_source_dir()
    print(f"Staging Tesseract build files from: {source}")

    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST)

    shutil.copy2(os.path.join(source, "tesseract.exe"), DEST)

    dll_count = 0
    for name in os.listdir(source):
        if name.lower().endswith(".dll"):
            shutil.copy2(os.path.join(source, name), DEST)
            dll_count += 1

    tessdata_src = os.path.join(source, "tessdata")
    tessdata_dest = os.path.join(DEST, "tessdata")
    os.makedirs(tessdata_dest, exist_ok=True)
    staged_tessdata = []
    for name in TESSDATA_FILES:
        src_file = os.path.join(tessdata_src, name)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, tessdata_dest)
            staged_tessdata.append(name)
        else:
            print(f"Warning: {name} not found in {tessdata_src}, skipping.")

    if "eng.traineddata" not in staged_tessdata:
        raise SystemExit(
            "eng.traineddata wasn't found -- the staged build would be "
            "unable to run OCR at all. Check your Tesseract install."
        )

    print(f"Staged tesseract.exe, {dll_count} DLLs, and {len(staged_tessdata)} "
          f"trained-data file(s) to: {DEST}")


if __name__ == "__main__":
    main()
