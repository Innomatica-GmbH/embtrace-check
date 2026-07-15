"""Build file scanner — collects and analyzes build files with an inference backend.

Supports CMake, Make, Meson, Conan, Cargo, Gradle, Go, Python, npm, Maven,
and Autotools build files.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from embtrace_check.core.log import get_logger

if TYPE_CHECKING:
    from embtrace_check.analyzer.engine import InferenceBackend
    from embtrace_check.analyzer.models import (
        BuildFileArtifact,
        BuildFileDependency,
        BuildFileInternalDep,
    )

logger = get_logger(__name__)


# File patterns to search for, mapped to their build-system type
BUILD_FILE_PATTERNS: list[tuple[str, str]] = [
    # C/C++ build systems
    ("CMakeLists.txt", "cmake"),
    ("**/CMakeLists.txt", "cmake"),
    ("**/*.cmake", "cmake"),
    ("Makefile", "make"),
    ("**/Makefile", "make"),
    ("*.mk", "make"),
    ("meson.build", "meson"),
    ("**/meson.build", "meson"),
    ("conanfile.py", "conan"),
    ("conanfile.txt", "conan"),
    ("configure.ac", "autotools"),
    ("configure.in", "autotools"),
    ("configure", "configure"),
    ("auto/lib/*/conf", "configure"),
    # Rust
    ("Cargo.toml", "cargo"),
    ("**/Cargo.toml", "cargo"),
    # Java
    ("build.gradle", "gradle"),
    ("**/build.gradle", "gradle"),
    ("build.gradle.kts", "gradle"),
    ("**/build.gradle.kts", "gradle"),
    ("**/dependencies.gradle", "gradle"),
    ("gradle/libs.versions.toml", "gradle"),
    ("**/libs.versions.toml", "gradle"),
    ("pom.xml", "maven"),
    ("**/pom.xml", "maven"),
    # Go
    ("go.mod", "go"),
    # Python
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("setup.cfg", "python"),
    ("requirements.txt", "python"),
    ("**/requirements.txt", "python"),
    ("**/requirements/*.txt", "python"),
    # Node.js
    ("package.json", "npm"),
    ("**/package.json", "npm"),
]


def collect_build_files(
    path: Path,
    max_depth: int = 5,
) -> list[tuple[Path, str]]:
    """Collect build files from a project directory.

    Args:
        path: Root directory to scan.
        max_depth: Maximum directory depth to search.

    Returns:
        List of (file_path, file_type) tuples.
    """
    found: list[tuple[Path, str]] = []
    seen_paths: set[Path] = set()

    for pattern, file_type in BUILD_FILE_PATTERNS:
        for match in path.glob(pattern):
            if not match.is_file():
                continue

            # Check depth
            try:
                relative = match.relative_to(path)
            except ValueError:
                continue
            if len(relative.parts) > max_depth:
                continue

            resolved = match.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            # Bare 'configure' must be a shell script (not a binary)
            if match.name == "configure" and file_type == "configure":
                try:
                    first_line = match.read_text(encoding="utf-8", errors="ignore")[:100]
                    if not first_line.startswith("#!"):
                        continue
                except OSError:
                    continue

            # Skip node_modules package.json files
            if "node_modules" in str(relative):
                continue

            found.append((match, file_type))
            logger.info("Found build file: %s (%s)", match, file_type)

    logger.info("Collected %d build files from %s", len(found), path)
    return found


def analyze_build_files(
    files: list[tuple[Path, str]],
    backend: InferenceBackend,
) -> tuple[
    list[BuildFileDependency],
    list[BuildFileArtifact],
    list[BuildFileInternalDep],
]:
    """Analyze build files using an inference backend.

    Args:
        files: List of (file_path, file_type) tuples from collect_build_files.
        backend: Inference backend to use for analysis.

    Returns:
        Tuple of (dependencies, artifacts, internal_deps) aggregated from all files.
    """
    all_deps: list[BuildFileDependency] = []
    all_artifacts: list[BuildFileArtifact] = []
    all_internal: list[BuildFileInternalDep] = []

    total = len(files)
    for i, (file_path, file_type) in enumerate(files, 1):
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", file_path, exc)
            continue

        logger.info("Analyzing [%d/%d] %s (%s)", i, total, file_path, file_type)
        result = backend.analyze(content, file_type)

        # Set source_file on all results
        for dep in result.dependencies:
            if not dep.source_file:
                dep.source_file = str(file_path)
            all_deps.append(dep)

        for artifact in result.artifacts:
            if not artifact.source_file:
                artifact.source_file = str(file_path)
            all_artifacts.append(artifact)

        for internal_dep in result.internal_deps:
            if not internal_dep.source_file:
                internal_dep.source_file = str(file_path)
            all_internal.append(internal_dep)

    logger.info(
        "Analysis complete: %d deps, %d artifacts, %d internal deps",
        len(all_deps), len(all_artifacts), len(all_internal),
    )
    return all_deps, all_artifacts, all_internal


def analyze_with_pipeline(
    project_path: Path,
    build_files: list[tuple[Path, str]],
    *,
    backend: InferenceBackend | None = None,
    enabled_tiers: set[int] | None = None,
    timeout_per_tool: float = 30.0,
) -> tuple[list[BuildFileDependency], list[BuildFileArtifact], list[BuildFileInternalDep]]:
    """Analyze build files using the multi-tier scanner pipeline.

    Runs all enabled tiers and merges results.  If no pipeline tiers produce
    results, falls back to the given backend (if provided).

    Args:
        project_path: Root directory of the project.
        build_files: List of (file_path, file_type) from collect_build_files.
        backend: Optional inference backend for LLM fallback.
        enabled_tiers: Which tiers to run (default: all).
        timeout_per_tool: Timeout in seconds for CLI tools.

    Returns:
        Tuple of (dependencies, artifacts, internal_deps).
    """
    from embtrace_check.analyzer.pipeline import run_pipeline

    deps, artifacts, internal = run_pipeline(
        project_path,
        build_files,
        enabled_tiers=enabled_tiers,
        timeout_per_tool=timeout_per_tool,
    )

    logger.info(
        "Pipeline complete: %d deps, %d artifacts, %d internal deps",
        len(deps), len(artifacts), len(internal),
    )
    return deps, artifacts, internal
