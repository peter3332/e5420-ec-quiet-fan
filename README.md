# Dell Latitude E5420 A14 — Quiet Fan Modification and EC Reverse Engineering

**From excessive fan noise to discovering undocumented firmware checksums.**

This project started with an everyday annoyance: the Dell Latitude E5420's lowest automatic fan stage ran at approximately **3,300 RPM** and was noticeably loud during light workloads. Our aim was a quieter **~2,500 RPM** first stage, without giving up higher fan speeds or thermal management.

That investigation led from Dell SMM fan requests to disassembling **ARC600** Embedded Controller code, modifying the *Minimum Drive* initialization and thermal table, reverse engineering Dell PFS packaging, and eventually discovering three separate additive integrity checksums in the EC firmware.

## Main outcome: M54FIX (October 24, 2026)

The original experimental **MIN54-QUIET** did achieve a low first fan speed, but plugging in AC power while the laptop was shut down (**S5**) could leave the EC unresponsive and the fan at maximum speed. Two other test images with **disjoint functional fan-control edits** produced similar symptoms.

Analysis of the stock EC revealed three zero-balanced 32-bit little-endian checksum regions:

| Region (informal name) | Half-open EC byte range | Compensation DWORD |
|---|---|---|
| BOOT-1 | `[0x1000,0x4400)` | `0x43FC` |
| BRIDGE | `[0x4400,0x5000)` | `0x4FFC` |
| BOOT-2 | `[0x5000,0x38000)` | `0x37FFC` |

The modified images did not preserve the checksum invariants. **M54FIX** retained the *exact same seven functional fan changes* as MIN54-QUIET, while correcting **four compensation bytes**. A second offline audit succeeded, flashing from FreeDOS and booting Xubuntu succeeded, BIOS AUTO fan control was observed, and the experimenter reported **one successful AC-insertion test in S5**.

This is a meaningful experimental result, **not a verified long-term or cross-device firmware upgrade**. We have not identified the exact instruction sequence linking a failed checksum to maximum fan duty and the unresponsive POWER button. We also have no independently validated EC recovery procedure.

## English technical documents

- [M54FIX case study](docs/M54FIX_AC_S5_CASE_STUDY.md) — experiments, all 11 changed EC bytes, exact hashes, test observations and limitations.
- [Three additive EC checksum regions](docs/EC_ADDITIVE_CHECKSUM.md) — how the format was discovered and why the first whole-image sum hypothesis required correction.
- [The original AC/S5 incident](docs/AC_S5_POSTMORTEM.md) — October 19 observations and the subsequent explanation.
- [ARC600 side findings and dead ends](docs/EC_ARC600_SIDE_FINDINGS.md) — boot code, timers, interrupts, indexed fan MMIO, TACH, flash records, service commands and keyboard decoding.
- [Historical thermal test results](docs/HISTORICAL_THERMAL_RESULTS.md) — 2,500 / 3,300 / 4,300 RPM curve and nine-minute tests on the uncorrected image.
- [Read-only UEFI/PE static reproduction](docs/REPRODUCE.md).
- [Offline checksum auditor and historical builder](docs/TOOLS.md).

The side-findings document preserves the important results of a multi-day deep dive. The large original notebooks and terminal transcripts are not included in this privacy-minimized English edition; their absence must not be confused with independent reproduction of every discovered execution path.

## Exact image identifiers (SHA-256)

```text
Stock A14 EC     dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96
MIN54-QUIET EC   b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab
M54FIX EC        90648894233eca7b25ee2fc53922254988c7a764e7f582c429ee34f175e59fb8
M54FIX EXE       45a735456487f09f94043c2405ef4df9bc4a84db4e8e5a05bd814572e5fa9f40
```

## Open licenses — free to reuse

**Please use, improve, translate and share this work. Commercial use is allowed.**

- **Python source code in `tools/`: [MIT License](LICENSE)** ([SPDX: MIT](https://spdx.org/licenses/MIT)). Copy, modify, redistribute, sublicense, or use the tools commercially, retaining the copyright and license notice.
- **Original research documentation: [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE-DOCS.md)** ([license overview](https://creativecommons.org/licenses/by/4.0/)). Copy, redistribute, translate, adapt, or use the writing commercially, crediting **peter3332**, linking to the license, and indicating any changes.

The grants cover material we are entitled to license; **third-party content and Dell firmware are not relicensed**. See [documentation-license details](LICENSE-DOCS.md).

## Reproduction and safety

The `tools/` directory contains only **Python source**, with no Dell-owned binary files. `audit_ec_additive_checksum.py` is read-only. `build_min54quiet_from_available.py` can reconstruct an **unsigned, modified updater file on disk** from verified inputs supplied separately by a researcher; **it does not flash** the laptop.

A rebuilt EXE **does not possess a valid Dell Authenticode signature**. Flashing nonstandard EC firmware can irreversibly damage the laptop; this publication is **technical research, not a recommendation to perform a flash or force manual fan control**.

**Scope:** one physical E5420 with Dell BIOS A14; measured RPM/temperature under limited conditions, one user-reported successful AC/S5 attempt after the checksum repair, and no physical EC flash readback or validated recovery path.

## Privacy and provenance

This public-edition source tree is designed to be committed to a **new, clean Git repository**. It intentionally excludes raw terminal logs, local user/hostname strings, personal correspondence, prepublication commit history, proprietary firmware and generated updater executables. The full original research archive remains separate and private.

For background, safety, and public-release provenance, see [PUBLICATION.md](PUBLICATION.md). The specific borrowed code credits described in the original private research are not incorporated into this source-only release.
