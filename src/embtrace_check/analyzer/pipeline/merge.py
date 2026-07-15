"""Merge engine — deduplicates scanner results across tiers.

Lower tier number = higher confidence.  When the same dependency is found
by multiple scanners, the result from the lowest tier wins.

Tier 5 (external tools like syft/trivy) undergoes additional filtering:
- File paths and CI artifacts are removed (not real dependencies)
- Only deps NOT already found by Tier 1-4 are kept (gap-filling mode)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from embtrace_check.analyzer.normalize import normalize_dep_name

if TYPE_CHECKING:
    from embtrace_check.analyzer.models import (
        BuildFileArtifact,
        BuildFileDependency,
        BuildFileInternalDep,
    )
    from embtrace_check.analyzer.pipeline.base import ScanResult

# Tier 5 noise patterns — deps matching these are filtered out
_TIER5_NOISE = re.compile(
    r"^(?:"
    r"actions/"              # GitHub Actions (actions/checkout, etc.)
    r"|github/"              # GitHub internal
    r"|google/"              # Google OSS-Fuzz actions
    r"|\.github/"            # .github/ workflow files
    r"|/repos/"              # Absolute repo paths
    r"|.*\.(?:yml|yaml|json|txt|toml|lock|gemspec|jar|war|properties|kts|gradle|xml)$"  # Config
    r")",
    re.IGNORECASE,
)


def _is_tier5_noise(name: str) -> bool:
    """Check if a Tier 5 dep name is noise (file paths, CI artifacts)."""
    return bool(_TIER5_NOISE.match(name))


def merge_results(
    results: list[ScanResult],
) -> tuple[list[BuildFileDependency], list[BuildFileArtifact], list[BuildFileInternalDep]]:
    """Merge scan results from multiple tiers.

    Deduplicates dependencies by normalized name.  The entry from the
    lowest tier (highest confidence) wins.  Version and source_file
    are taken from the winning entry.

    Tier 5 dependencies are filtered: file paths and CI artifacts are
    removed, and only deps not already found by Tier 1-4 are kept.

    Artifacts and internal deps are deduplicated by path/project name.

    Returns:
        Merged (dependencies, artifacts, internal_deps).
    """
    # --- Dependencies: deduplicate by normalized name, lowest tier wins ---
    # First pass: collect Tier 1-4 deps
    dep_best: dict[str, tuple[int, BuildFileDependency]] = {}

    for result in results:
        if result.tier >= 5:
            continue  # handle Tier 5 in second pass
        for dep in result.dependencies:
            key = normalize_dep_name(dep.name)
            existing = dep_best.get(key)
            if existing is None or result.tier < existing[0]:
                dep_best[key] = (result.tier, dep)

    # Second pass: Tier 5 — only keep non-noise deps not already found
    for result in results:
        if result.tier < 5:
            continue
        for dep in result.dependencies:
            if _is_tier5_noise(dep.name):
                continue
            key = normalize_dep_name(dep.name)
            if key not in dep_best:
                dep_best[key] = (result.tier, dep)

    merged_deps = [dep for _, dep in sorted(dep_best.values(), key=lambda x: x[1].name.lower())]

    # --- Artifacts: deduplicate by path ---
    seen_paths: set[str] = set()
    merged_artifacts: list[BuildFileArtifact] = []
    for result in sorted(results, key=lambda r: r.tier):
        for art in result.artifacts:
            if art.path not in seen_paths:
                seen_paths.add(art.path)
                merged_artifacts.append(art)

    # --- Internal deps: deduplicate by project name ---
    seen_projects: set[str] = set()
    merged_internal: list[BuildFileInternalDep] = []
    for result in sorted(results, key=lambda r: r.tier):
        for idep in result.internal_deps:
            key = idep.project.lower()
            if key not in seen_projects:
                seen_projects.add(key)
                merged_internal.append(idep)

    return merged_deps, merged_artifacts, merged_internal
