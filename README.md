# embtrace-check

**Free CRA Readiness Check collector** — one command in your project folder,
and within 24 hours you receive a report showing where your product stands
with the [EU Cyber Resilience Act](https://embtrace.dev/en/cra-nis2-guide.html):
traffic-light readiness status, your full component inventory, and known
vulnerabilities with severity.

This collector is **open source for one reason: so you can verify exactly
what leaves your machine.**

## What it transmits — and what it never does

Transmitted (JSON, ~a few kB):

- names, versions and package ecosystems of your dependencies
  (from lockfiles and build files: Conan, vcpkg, CMake, Cargo, npm/yarn/pnpm,
  Python incl. uv, Go, Maven/Gradle, Meson, and more),
- names and versions of FPGA IP cores
  (AMD/Xilinx Vivado `.hwh`/`.xci`, Microchip Libero Tcl/`.cxf`,
  Intel/Altera Quartus `*_hw.tcl`),
- the project folder name (hash it with `--anonymize`),
- scan statistics (number of build files, tool version).

**Never transmitted:** source code, file paths, file contents, configuration,
credentials. The supplier of an FPGA IP core is known locally but
deliberately **not** transmitted — names, versions and ecosystems only.
See for yourself before sending anything:

```bash
embtrace-check . --dry-run     # prints the exact payload, uploads nothing
```

## Usage

1. Get your free one-time code at **<https://embtrace.dev/check>**
   (the report goes to the e-mail address you register there).
2. Run the collector in your project folder:

```bash
pipx install embtrace-check         # or: pip install embtrace-check,
                                    #     or download the standalone binary
embtrace-check . --code CHK-XXXX-YYYY
```

3. Your report arrives within 24 hours. The code is valid for one check.

More options: `embtrace-check --help` — including `--output payload.json`
for air-gapped environments (send the file by mail) and `--with-tools` to
additionally use native package-manager CLIs for higher-fidelity results.

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | success |
| 1    | error (network, invalid code, …) |
| 2    | no components found — declare dependencies manually in `embtrace-deps.yaml` |

## Privacy

Data is processed exclusively on Innomatica's own servers in Germany and is
never shared or sold. Full notes: <https://embtrace.dev/check-privacy>.

## About

`embtrace-check` is the free entry point to
[embtrace](https://embtrace.dev) — the CRA/NIS2 compliance toolchain for
embedded software teams by [Innomatica GmbH](https://embtrace.dev/impressum.html).
The server side (enrichment, vulnerability monitoring, reports) is a
commercial product; this repository contains the complete client.

Maintained by Innomatica; the roadmap follows the product. Issues and PRs are
welcome — please report security topics per [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Innomatica GmbH
