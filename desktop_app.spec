# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone Windows desktop build.

Build steps (from the repo root, inside the project's venv, with
requirements-build.txt installed):

    python packaging/stage_tesseract.py
    pyinstaller desktop_app.spec

Output is a one-folder bundle at dist/AlcoholLabelVerification/ --
AlcoholLabelVerification.exe plus everything it needs alongside it,
including the bundled Tesseract OCR binary and its English trained-data
file (see packaging/stage_tesseract.py). Ship/zip the whole folder --
double-clicking the .exe opens the app in the default browser. A console
window stays open while it runs; closing it stops the app.

Uses packaging/label_verifier.ico as the exe's icon. To sign the built
exe afterward, see packaging/sign_exe.ps1.
"""

import os

a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/templates", "app/templates"),
        ("app/static", "app/static"),
        ("app/schema.sql", "app"),
        ("packaging/tesseract", "tesseract"),
    ],
    hiddenimports=["waitress"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# PyInstaller's binary/data reclassification moves the bundled Tesseract
# DLLs (originally under datas, "tesseract/...") into a.binaries -- that
# part's fine. But scanning tesseract.exe's own PE imports, it ALSO adds a
# second, unprefixed top-level copy of each DLL it depends on (e.g. a bare
# "libtesseract-5.dll" alongside the "tesseract/libtesseract-5.dll" already
# staged) -- doubling their size for no reason (100+ MB for
# libtesseract-5.dll alone). tesseract.exe only ever needs its DLLs to sit
# right next to itself in tesseract/, since pytesseract shells out to it as
# a subprocess -- so that top-level copy is wasted space for it.
#
# BUT: several of those DLL names (libffi, zlib, libpng, ...) are common
# shared libraries that something else in this bundle genuinely needs at
# the top level too (e.g. CPython's own _ctypes extension loads a
# top-level libffi-8.dll) -- removing those breaks that unrelated import,
# even though the file matches "sourced from packaging/tesseract" (the
# tesseract install just happens to ship a same-named copy). Rather than
# try to prove a given DLL is safe to drop, only remove the two that are
# unambiguously Tesseract/Leptonica-specific and large enough to matter --
# nothing else in this app's dependency stack touches those libraries.
_dedupe_only = {"libtesseract-5.dll", "libleptonica-6.dll"}
a.binaries = [
    b for b in a.binaries
    if not (os.path.dirname(b[0]) == "" and os.path.basename(b[0]) in _dedupe_only)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AlcoholLabelVerification",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon="packaging/label_verifier.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AlcoholLabelVerification",
)
