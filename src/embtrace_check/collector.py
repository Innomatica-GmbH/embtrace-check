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
from embtrace_check.core.exceptions import CheckCollectionError
from embtrace_check.payload import CheckComponent, CheckStats
from embtrace_check.sbom.scanner import scan_directory_recursive

if TYPE_CHECKING:
    from pathlib import Path

#: Deterministic pipeline tiers that need no tooling on the host.
_DEFAULT_TIERS = frozenset({2, 4})
#: Tier 1 adds native CLI tools (cargo, go, npm, …) when present on the host.
_TOOL_TIER = 1

#: Confidence assigned to lockfile-derived components (structured parse).
_LOCKFILE_CONFIDENCE = 0.95
#: Confidence for manifest-constraint floors (">=" — version unconfirmed).
_MANIFEST_CONFIDENCE = 0.7
_LOCKFILE_TIER = 2

#: Build-script name-token ecosystems — the only place the skip list
#: may drop a name (npm/pypi homonyms like bcrypt/threads/numpy are
#: real packages).
_NAME_ONLY_ECOSYSTEMS = frozenset({
    "cmake", "meson", "make", "autotools", "configure", "generic",
})


def collect_components(
    path: Path,
    *,
    with_tools: bool = False,
    max_depth: int = 5,
    include_declared_metadata: bool = True,
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
    # pinned versions), so they are inserted first. Manifest-constraint
    # floors already lost against resolved versions inside
    # scan_directory_recursive (prefer_locked); the survivors are labelled
    # honestly — a ">=" floor is not a lockfile fact.
    from embtrace_check.sbom.skiplist import is_skipped

    # Identity of a component is (name, version, ecosystem) — never the
    # name alone: npm regularly nests two versions of one package, and
    # the older nested one is often the vulnerable one (order
    # collector-mehrfachversionen).
    merged: dict[tuple[str, str], CheckComponent] = {}
    for dep in scan_directory_recursive(path, max_depth=max_depth):
        key = (normalize_dep_name(dep.name), dep.version)
        if key in merged:
            continue
        # Curated skip list (build tools, system libs) applies only to
        # name tokens from build scripts — a resolved lockfile entry is
        # a real package regardless of its name (npm bcrypt/threads/util
        # are homonyms, not tooling); declarations are never skipped.
        if (
            not dep.declared
            and dep.ecosystem in _NAME_ONLY_ECOSYSTEMS
            and is_skipped(dep.name)
        ):
            continue
        # Entries from embtrace-deps.yaml are the customer's own SBOM
        # declaration: they keep the metadata written there (opt-out via
        # include_declared_metadata) and are labelled "declared" so the
        # server can tell declaration from discovery apart.
        if dep.declared:
            merged[key] = CheckComponent(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                source_type="declared",
                tier=_LOCKFILE_TIER,
                confidence=1.0,
                supplier=(dep.supplier or "") if include_declared_metadata else "",
                license=(dep.license or "") if include_declared_metadata else "",
                purl=(dep.purl or "") if include_declared_metadata else "",
                cpe=(dep.cpe or "") if include_declared_metadata else "",
            )
            continue
        is_floor = dep.source_kind == "manifest"
        merged[key] = CheckComponent(
            name=dep.name,
            version=dep.version,
            ecosystem=dep.ecosystem,
            source_type="manifest" if is_floor else "lockfile",
            tier=_LOCKFILE_TIER,
            confidence=_MANIFEST_CONFIDENCE if is_floor else _LOCKFILE_CONFIDENCE,
        )

    # Path 2: build-file pipeline (deterministic tiers only).
    tiers = set(_DEFAULT_TIERS | {_TOOL_TIER}) if with_tools else set(_DEFAULT_TIERS)
    build_files = collect_build_files(path, max_depth=max_depth)
    pipeline_deps, _artifacts, _internal = run_pipeline(
        path, build_files, enabled_tiers=tiers
    )
    seen_names = {name for name, _version in merged}
    for pdep in pipeline_deps:
        if normalize_dep_name(pdep.name) in seen_names:
            continue
        if pdep.ecosystem in _NAME_ONLY_ECOSYSTEMS and is_skipped(pdep.name):
            continue
        key = (normalize_dep_name(pdep.name), pdep.version)
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

    # Path 3: Yocto/Buildroot BUILD OUTPUT — what is actually in the
    # customer's image (run the check in the build directory).
    from embtrace_check.sbom.buildoutput import scan_build_output

    build_output_deps, build_output_sources = scan_build_output(
        path, max_depth=max_depth,
    )
    for dep in build_output_deps:
        # Resolved, installed packages — the skip list never applies.
        key = (normalize_dep_name(dep.name), dep.version)
        if key in merged:
            continue
        merged[key] = CheckComponent(
            name=dep.name,
            version=dep.version,
            ecosystem=dep.ecosystem,
            source_type="build-output",
            tier=_LOCKFILE_TIER,
            confidence=_LOCKFILE_CONFIDENCE,
        )

    components = list(merged.values())
    ecosystems = sorted({c.ecosystem for c in components if c.ecosystem})
    stats = CheckStats(
        build_files_scanned=len(build_files),
        ecosystems=ecosystems,
        build_output_sources=build_output_sources,
    )
    return components, stats
