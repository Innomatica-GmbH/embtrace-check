"""Deterministic build-file parsers.

Each parser module exposes a ``parse(content: str) -> list[str]`` function
that extracts dependency names from a specific build-file format.

The ``PARSERS`` dict maps file_type → parse function, matching the types
used by ``scanner.BUILD_FILE_PATTERNS``.
"""

from __future__ import annotations

from collections.abc import Callable

from embtrace_check.analyzer.parsers.autotools import parse as parse_autotools
from embtrace_check.analyzer.parsers.cargo import parse as parse_cargo
from embtrace_check.analyzer.parsers.cmake import parse as parse_cmake
from embtrace_check.analyzer.parsers.configure import parse as parse_configure
from embtrace_check.analyzer.parsers.gomod import parse as parse_go
from embtrace_check.analyzer.parsers.gradle import parse as parse_gradle
from embtrace_check.analyzer.parsers.makefile import parse as parse_make
from embtrace_check.analyzer.parsers.maven import parse as parse_maven
from embtrace_check.analyzer.parsers.meson import parse as parse_meson
from embtrace_check.analyzer.parsers.npm import parse as parse_npm
from embtrace_check.analyzer.parsers.python import parse as parse_python

# Maps file_type (from scanner.BUILD_FILE_PATTERNS) → parser function
PARSERS: dict[str, Callable[[str], list[str]]] = {
    "cmake": parse_cmake,
    "meson": parse_meson,
    "cargo": parse_cargo,
    "go": parse_go,
    "python": parse_python,
    "npm": parse_npm,
    "gradle": parse_gradle,
    "maven": parse_maven,
    "autotools": parse_autotools,
    "configure": parse_configure,
    "make": parse_make,
    "conan": parse_cmake,  # conanfile.py/txt handled separately; fallback to cmake
}
