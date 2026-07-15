# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone embtrace-check binary.

Build with:
    pyinstaller embtrace-check.spec --clean
"""

from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["src/embtrace_check/cli.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "embtrace_check.payload",
        "embtrace_check.collector",
        "embtrace_check.upload",
        "embtrace_check.analyzer.pipeline.tier1_cli",
        "embtrace_check.analyzer.pipeline.tier2_structured",
        "embtrace_check.analyzer.pipeline.tier4_regex",
        "embtrace_check.analyzer.pipeline.merge",
        "embtrace_check.analyzer.scanner",
        "embtrace_check.analyzer.normalize",
        "embtrace_check.sbom.scanner",
        "embtrace_check.core.exceptions",
        *collect_submodules("embtrace_check.analyzer.parsers"),
        "yaml",
        "pydantic",
        "click",
        "rich",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="embtrace-check",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
