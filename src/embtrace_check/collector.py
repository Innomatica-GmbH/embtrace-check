"""Dependency collection for the CRA Readiness Check.

Combines the two deterministic detection paths that already power embtrace:

1. :func:`embtrace.sbom.scanner.scan_directory_recursive` — lockfiles and
   manifests (16 formats, high confidence).
2. :func:`embtrace.analyzer.pipeline.run_pipeline` — build-file analysis via
   the multi-tier pipeline, restricted to the deterministic tiers (2 = struct-
   ured parsers, 4 = regex; tier 1 CLI tools optional via ``with_tools``).

No LLM, no tree-sitter, no external tools by default — the collector must run
anywhere, instantly, with zero setup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from embtrace_check.analyzer.normalize import normalize_dep_name
from embtrace_check.analyzer.pipeline import run_pipeline
from embtrace_check.analyzer.scanner import collect_build_files
from embtrace_check.payload import CheckComponent, CheckStats
from embtrace_check.core.exceptions import CheckCollectionError
from embtrace_check.sbom.scanner import scan_directory_recursive

if TYPE_CHECKING:
    from pathlib import Path

#: Deterministic pipeline tiers that need no tooling on the host.
_DEFAULT_TIERS = frozenset({2, 4})
#: Tier 1 adds native CLI tools (cargo, go, npm, …) when present on the host.
_TOOL_TIER = 1

#: Confidence assigned to lockfile-derived components (structured parse).
_LOCKFILE_CONFIDENCE = 0.95
_LOCKFILE_TIER = 2


def collect_components(
    path: Path,
    *,
    with_tools: bool = False,
    max_depth: int = 5,
) -> tuple[list[CheckComponent], CheckStats]:
    """Collect deduplicated dependency metadata from a project directory.

    Args:
        path: Project root to scan.
        with_tools: Also run tier 1 (native CLI tools) of the pipeline.
        max_depth: Maximum directory depth for both detection paths.

    Returns:
        Tuple of (components sorted by insertion source, scan statistics).

    Raises:
        CheckCollectionError: If ``path`` is not a readable directory.
    """
    if not path.is_dir():
        msg = f"Not a directory: {path}"
        raise CheckCollectionError(msg)

    # Path 1: lockfiles / manifests — these win on conflict (they carry
    # pinned versions), so they are inserted first.
    merged: dict[str, CheckComponent] = {}
    for dep in scan_directory_recursive(path, max_depth=max_depth):
        key = normalize_dep_name(dep.name)
        if key in merged:
            continue
        merged[key] = CheckComponent(
            name=dep.name,
            version=dep.version,
            ecosystem=dep.ecosystem,
            source_type="lockfile",
            tier=_LOCKFILE_TIER,
            confidence=_LOCKFILE_CONFIDENCE,
        )

    # Path 2: build-file pipeline (deterministic tiers only).
    tiers = set(_DEFAULT_TIERS | {_TOOL_TIER}) if with_tools else set(_DEFAULT_TIERS)
    build_files = collect_build_files(path, max_depth=max_depth)
    pipeline_deps, _artifacts, _internal = run_pipeline(
        path, build_files, enabled_tiers=tiers
    )
    for pdep in pipeline_deps:
        key = normalize_dep_name(pdep.name)
        if key in merged:
            continue
        merged[key] = CheckComponent(
            name=pdep.name,
            version=pdep.version,
            ecosystem=pdep.ecosystem,
            source_type=pdep.detection_method or "build-file",
            tier=pdep.tier,
            confidence=pdep.confidence,
        )

    components = list(merged.values())
    ecosystems = sorted({c.ecosystem for c in components if c.ecosystem})
    stats = CheckStats(build_files_scanned=len(build_files), ecosystems=ecosystems)
    return components, stats
