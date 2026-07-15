"""Payload models for the CRA Readiness Check upload (schema version 1).

The payload deliberately carries dependency *metadata only*: component names,
versions and ecosystems. No file paths, no source code, no hostnames. This is
the data-minimisation promise shown to the prospect via ``--dry-run``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION: Final = 1

#: Hard upper bound for a serialised payload (bytes) — mirrored server-side.
MAX_PAYLOAD_BYTES = 2_000_000


class CheckComponent(BaseModel):
    """One detected third-party component (metadata only)."""

    name: str
    version: str = ""
    ecosystem: str = ""
    source_type: str = ""  # e.g. "lockfile", "regex-cmake", "cargo-metadata"
    tier: int = 0
    confidence: float = 1.0


class CheckStats(BaseModel):
    """Aggregate statistics about the scan (no paths, counts only)."""

    build_files_scanned: int = 0
    ecosystems: list[str] = Field(default_factory=list)


class CheckPayload(BaseModel):
    """Complete upload payload for ``POST /api/v1/check/submit``."""

    schema_version: Literal[1] = SCHEMA_VERSION
    voucher: str
    contact_email: str
    collected_at: str
    tool_version: str
    project_label: str
    components: list[CheckComponent]
    stats: CheckStats


def anonymize_label(label: str) -> str:
    """Replace a project label with a short stable hash.

    Args:
        label: Human-readable project label (usually the directory name).

    Returns:
        First 12 hex chars of the SHA-256 of the label, prefixed for clarity.
    """
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    return f"anon-{digest}"


def build_payload(
    *,
    voucher: str,
    contact_email: str,
    tool_version: str,
    project_label: str,
    components: list[CheckComponent],
    stats: CheckStats,
    anonymize: bool = False,
) -> CheckPayload:
    """Assemble the upload payload with a UTC collection timestamp.

    Args:
        voucher: Partner voucher / campaign code.
        contact_email: Where the report should be sent.
        tool_version: embtrace-check version string.
        project_label: Project name; hashed when ``anonymize`` is set.
        components: Detected components (deduplicated).
        stats: Aggregate scan statistics.
        anonymize: Replace the project label with a stable hash.

    Returns:
        A validated :class:`CheckPayload`.
    """
    label = anonymize_label(project_label) if anonymize else project_label
    return CheckPayload(
        voucher=voucher,
        contact_email=contact_email,
        collected_at=datetime.now(UTC).isoformat(timespec="seconds"),
        tool_version=tool_version,
        project_label=label,
        components=sorted(components, key=lambda c: (c.name.lower(), c.ecosystem)),
        stats=stats,
    )
