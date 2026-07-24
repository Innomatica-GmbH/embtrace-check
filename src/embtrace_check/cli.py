"""CLI entry point for embtrace-check (standalone CRA Readiness Check collector).

Usage:
    embtrace-check . --code CHK-ACME-7F3A     # one-time code from embtrace_check.dev/check
    embtrace-check . --dry-run                # show exactly what would be sent
    embtrace-check . --output payload.json    # offline / firewall fallback
    embtrace-check . --voucher STOIL-2026 --email cto@example.com   # partner voucher

Exit codes: 0 = success, 1 = error, 2 = no components found.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from embtrace_check import __version__
from embtrace_check.collector import collect_components
from embtrace_check.core.exceptions import EmbtraceError
from embtrace_check.payload import build_payload
from embtrace_check.upload import DEFAULT_SUBMIT_URL, serialize_payload, upload_payload

_PRIVACY_URL = "https://embtrace.dev/check-privacy"

console = Console(stderr=True)
_stdout = Console(soft_wrap=True)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="embtrace-check")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option(
    "--code",
    default="",
    help="Personal one-time code from https://embtrace.dev/check (report goes "
    "to the address you registered there).",
)
@click.option("--voucher", default="", help="Partner voucher / campaign code.")
@click.option(
    "--email",
    "contact_email",
    default="",
    help="E-mail address the report is sent to (required with --voucher).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the exact payload that would be uploaded, upload nothing.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the payload to a file instead of uploading (offline fallback).",
)
@click.option(
    "--anonymize",
    is_flag=True,
    help="Replace the project name with a stable hash in the payload.",
)
@click.option(
    "--with-tools",
    is_flag=True,
    help="Additionally use native package-manager CLIs (cargo, go, npm, ...) if installed.",
)
@click.option(
    "--url",
    default=DEFAULT_SUBMIT_URL,
    show_default=False,
    help="Override the submit endpoint (testing).",
)
def main(  # noqa: PLR0913 — CLI surface, mirrors documented flags
    path: Path,
    code: str,
    voucher: str,
    contact_email: str,
    dry_run: bool,
    output: Path | None,
    anonymize: bool,
    with_tools: bool,
    url: str,
) -> None:
    """Collect dependency metadata for the embtrace CRA Readiness Check.

    Scans PATH (default: current directory) for lockfiles and build files,
    then uploads component names/versions — never code, never file paths.
    Privacy notice: https://embtrace.dev/check-privacy
    """
    try:
        _run(
            path=path,
            code=code,
            voucher=voucher,
            contact_email=contact_email,
            dry_run=dry_run,
            output=output,
            anonymize=anonymize,
            with_tools=with_tools,
            url=url,
        )
    except EmbtraceError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)


def _run(  # noqa: PLR0913 — mirrors the CLI surface
    *,
    path: Path,
    code: str,
    voucher: str,
    contact_email: str,
    dry_run: bool,
    output: Path | None,
    anonymize: bool,
    with_tools: bool,
    url: str,
) -> None:
    """Execute collect → assemble → (print | write | upload)."""
    uploading = not dry_run and output is None
    if uploading:
        if code and voucher:
            console.print("[red]Error:[/red] use either --code or --voucher, not both.")
            sys.exit(1)
        if code:
            # Personal one-time token: the server knows the registered address.
            voucher = code
        elif not voucher:
            console.print(
                "[red]Error:[/red] a code is required for upload. Get your free "
                "one-time code at https://embtrace.dev/check"
            )
            sys.exit(1)
        elif "@" not in contact_email:
            console.print("[red]Error:[/red] --email must be a valid address (report delivery).")
            sys.exit(1)
        if code and contact_email and "@" not in contact_email:
            console.print("[red]Error:[/red] --email must be a valid address (report delivery).")
            sys.exit(1)

    console.print(f"[bold]embtrace-check[/bold] {__version__} — scanning {path.resolve().name}/")
    components, stats = collect_components(path, with_tools=with_tools)

    if not components:
        console.print(
            "[yellow]No components found.[/yellow] If this project has no lockfiles, "
            "declare dependencies manually in embtrace-deps.yaml and re-run."
        )
        sys.exit(2)

    console.print(
        f"Found [bold]{len(components)}[/bold] components "
        f"({', '.join(stats.ecosystems) or 'no ecosystem info'}) "
        f"in {stats.build_files_scanned} build files."
    )

    payload = build_payload(
        voucher=voucher or code or "DRY-RUN",
        # With a personal --code the address stays empty — the server fills it
        # from the registration; the placeholder is for dry-run/offline only.
        contact_email=contact_email or ("" if code else "dry-run@localhost"),
        tool_version=__version__,
        project_label=path.resolve().name,
        components=components,
        stats=stats,
        anonymize=anonymize,
    )

    if dry_run:
        console.print("[dim]-- payload that would be uploaded (nothing was sent): --[/dim]")
        _stdout.print_json(payload.model_dump_json())
        console.print(f"[dim]Privacy notice: {_PRIVACY_URL}[/dim]")
        return

    if output is not None:
        output.write_bytes(serialize_payload(payload))
        console.print(
            f"[green]Payload written to {output}.[/green] "
            "Send it to support@innomatica.de to receive your report."
        )
        return

    reference = upload_payload(payload, url=url)
    destination = contact_email or "your registered address"
    console.print(
        f"[green]Uploaded.[/green] Reference: [bold]{reference}[/bold] — "
        f"your CRA readiness report will be sent to {destination} within 24 hours."
    )


if __name__ == "__main__":
    main()
