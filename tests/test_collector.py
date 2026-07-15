"""Tests for the check collector (lockfile + pipeline merge)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from embtrace_check.analyzer.normalize import normalize_dep_name
from embtrace_check.collector import collect_components
from embtrace_check.core.exceptions import CheckCollectionError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def demo_project(tmp_path: Path) -> Path:
    """A minimal polyglot project: Python lockfile + CMake build file."""
    (tmp_path / "requirements.txt").write_text(
        "requests==2.31.0\nurllib3==2.2.1\n", encoding="utf-8"
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\n"
        "project(demo)\n"
        "find_package(OpenSSL REQUIRED)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_collects_from_lockfile_and_build_file(demo_project: Path) -> None:
    components, stats = collect_components(demo_project)
    names = {normalize_dep_name(c.name) for c in components}
    assert normalize_dep_name("requests") in names
    assert normalize_dep_name("openssl") in names
    assert stats.build_files_scanned >= 1
    assert "pypi" in stats.ecosystems


def test_lockfile_entries_carry_versions_and_win_dedup(demo_project: Path) -> None:
    components, _stats = collect_components(demo_project)
    by_norm = {normalize_dep_name(c.name): c for c in components}
    req = by_norm[normalize_dep_name("requests")]
    assert req.version == "2.31.0"
    assert req.source_type == "lockfile"
    # dedup: every normalized name appears exactly once
    norms = [normalize_dep_name(c.name) for c in components]
    assert len(norms) == len(set(norms))


def test_empty_directory_yields_no_components(tmp_path: Path) -> None:
    components, stats = collect_components(tmp_path)
    assert components == []
    assert stats.ecosystems == []


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(CheckCollectionError):
        collect_components(tmp_path / "does-not-exist")
