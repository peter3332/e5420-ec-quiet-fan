# Dell Latitude E5420 A14 — Quiet Fan Modification & ARC600 EC Reverse Engineering

**A noisy 3,300 RPM fan led us into the Dell Embedded Controller's ARM-independent ARC600 firmware. We mapped its fan-drive initialization, discovered three temperature–RPM profiles, measured how the automatic fan curve behaves, and uncovered internal firmware checksums that proved essential to our experimental repair.**

**This repository is about making an E5420 quieter while understanding exactly what we changed — not merely about checksums.**

> **In brief:** On one Dell Latitude E5420 (BIOS A14), we reduced the first BIOS-managed fan stage from **~3,300 RPM to ~2,525 RPM** and the second from **~3,800 RPM to ~3,350 RPM**, leaving the **~4,300 RPM third stage** in place. After identifying and correcting two violated additive checksum words, the **M54FIX** image booted and showed the desired fan behavior; **one** AC-insertion test in the powered-off state (S5) was reported successful. This is **experimental, single-device evidence**, not a validated firmware upgrade for other machines.

## 1. The practical result: quieter automatic cooling

Unlike forcing a fixed speed through Linux/SMM, the goal was to **retain BIOS AUTO**, including automatic stop/start and higher-speed thermal protection.

| Fan stage | Factory A14 / original BIOS AUTO | MIN54-QUIET and M54FIX target | Observed on the historical quiet profile |
|---|---:|---:|---:|
| First | 3,300 RPM | **2,500 RPM** | **~2,522–2,528 RPM** |
| Second | 3,800 RPM | **3,300 RPM** | **~3,340–3,352 RPM** |
| Third | 4,300 RPM | **4,300 RPM (unchanged)** | **~4,290–4,311 RPM** |

A **nine-minute synthetic BIOS AUTO thermal test** of the historical MIN54-QUIET completed with an **85°C stop limit**; the highest CPU core temperature visible in the terminal samples was approximately **83°C**. The historical MIN54-QUIET was later **withdrawn** because connecting AC power in S5 could leave the EC stuck. These historical thermal measurements do **not** constitute a full nine-minute retest of the checksum-corrected M54FIX.

We also tested a more aggressive ~2,260 RPM first stage (MIN54-AUTO). It was quiet at first but could escalate to **~3,800 RPM sooner during sustained single-core load**; the ~2,500/3,300 RPM curve was a more useful trade-off on the tested machine. See [comparative thermal results](docs/HISTORICAL_THERMAL_RESULTS.md).

## 2. Finding the fan's *Minimum Drive* setting in ARC600

Disassembly of the extracted **229,376-byte (\`0x38000\`) stock EC image** revealed **two** initialization paths with a matching indexed register write:

| Stock EC location | Code sequence (simplified) | Changed operand | Stock → quiet value |
|---|---|---|---|
| Around \`0x2748\` | \`r0=0xF01480, r1=0x87, r2=0x66\` → wrapper \`0x1474\` | **\`0x02750\`** | **\`0x66 → 0x54\`** |
| Around \`0x164CE\` | \`r0=0xF01480, r1=0x87, r2=0x66\` → wrapper \`0x5784\` | **\`0x164D6\`** | **\`0x66 → 0x54\`** |

The underlying routines write the **index** to \`[0xF01480+4] = 0xF01484\` and the **value** to \`[0xF01480+8] = 0xF01488\`. Adjacent settings form the pattern \`0x85=0x19\`, \`0x86=0x10\`, \`0x87=0x66\`, \`0x88=0xF5\`. Those values resemble *Spin Up / Max Step / Minimum Drive / Valid TACH* controls in other SMSC/Microchip fan-controller implementations.

**What is proven:** the actual two instruction operands, indexed hardware writes, and measured speed effects. **What is inferred:** that index \`0x87\` is formally named *Minimum Drive* for this exact EC; we do **not** have a matching vendor register map or electrical PWM measurements.

The experimental manual Dell SMM requests exposed a lower RPM floor as this value was decreased:

| Both initialization values | Historical variant | Manual request | Actual settled speed |
|---|---|---|---|
| \`0x66\` | Stock A14 | 2,000 RPM | ~2,725 RPM |
| \`0x60\` | MIN60 | 2,000 RPM | ~2,575–2,581 RPM |
| \`0x58\` | MIN58 | 1,500 RPM | ~2,368–2,377 RPM |
| **\`0x54\`** | **MIN54** | 1,500 RPM | **~2,263–2,270 RPM** |
| \`0x50\` | MIN50 | 1,500–2,000 RPM | **Unstable oscillation** |

These were **manual SMM speed-request tests**, not the BIOS AUTO table values. Changing *Minimum Drive* alone did **not** change the factory ~3,300 RPM automatic first-stage target. That required finding a different firmware structure.

## 3. Discovery of three temperature–RPM profile tables

A pointer table in the EC image led to **three 36-byte (\`0x24\`) records**:

| Pointer stored at | Record header | First normal 4-byte stage | Working interpretation |
|---|---|---|---|
| **\`0x216B8\`** | \`0x216C8\` | **\`0x216D0\`** | **Profile A — very likely CPU** |
| **\`0x216BC\`** | \`0x216EC\` | **\`0x216F4\`** | **Profile B — sensor unknown** |
| **\`0x216C0\`** | \`0x21710\` | **\`0x21718\`** | **Profile C — sensor unknown** |

Each normal stage we identified consists of two single-byte temperatures followed by a **16-bit little-endian RPM setpoint**. The first three normal stages in each profile are:

| Profile | Raw EC stage offset | Temperature pair (°C) | Target RPM |
|---|---|---|---:|
| **A** | \`0x216D0\` | **50 / 72** | **2,500** in M54FIX; 3,300 stock |
| **A** | \`0x216D4\` | **65 / 80** | **3,300** in M54FIX; stock 65 / 78 and 3,800 |
| **A** | \`0x216D8\` | **74 / 85** | **4,300**, unchanged |
| **B** | \`0x216F4\` | 43 / 50 | 3,300 |
| **B** | \`0x216F8\` | 47 / 54 | 3,800 |
| **B** | \`0x216FC\` | 51 / 58 | 4,300 |
| **C** | \`0x21718\` | 48 / 53 | 3,300 |
| **C** | \`0x2171C\` | 51 / 56 | 3,800 |
| **C** | \`0x21720\` | 54 / 59 | 4,300 |

**Actual edited bytes at profile A offset \`0x216D0\` in MIN54-QUIET / M54FIX:**

\`\`\`text
32 48 C4 09 | 41 50 E4 0C | 4A 55 CC 10
50 72 2500  | 65 80 3300  | 74 85 4300
\`\`\`

The stock first three profile A entries were:

\`\`\`text
32 48 E4 0C | 41 4E D8 0E | 4A 55 CC 10
50 72 3300  | 65 78 3800  | 74 85 4300
\`\`\`

The header at \`0x216CC\` includes \`81 43 00 00\`; \`0x43 = 67\` agrees with an approximately **67°C observed fan-start condition** on the Dell-reported CPU sensor. The entire 36-byte structure has **not** been decoded; special values including \`0x5356\` must **not** be mistaken for ordinary fan RPM setpoints. Only profile A has been linked convincingly to CPU behavior; assigning profiles B and C to specific sensors would be speculation.

## 4. Hysteresis: an evidence-based model, not yet a disassembled algorithm

A natural interpretation of each temperature pair is a **lower threshold for returning to a slower stage** and an **upper threshold for escalating**. For the M54FIX profile A, this gives a *provisional* state-transition model:

| Transition | Heating: proposed up threshold | Cooling: proposed down threshold |
|---|---:|---:|
| Fan OFF ↔ first stage | **~67°C**, suggested by the header and tests | **~50°C**, consistent with observed stops |
| First ↔ second stage | **~72°C**, observed on quiet-profile tests | **~65°C**, inferred from next row |
| Second ↔ third stage | **~80°C**, behaviorally supported near 80–81°C | **~74°C**, inferred from next row |

This is **not a confirmed EC hysteresis implementation**. In particular, our historical QUIET→QUIET2 edit **\`0x216D1: 0x48→0x4A\` (72→74°C)** shifted the observed first-to-second transition accordingly, but the proposed **65°C and 74°C downward thresholds** were **not independently measured**. Delays, filtered temperatures, startup logic and arbitration between profiles may also influence the actual fan stage.

The [full thermal-profile map](docs/THERMAL_PROFILE_MAP.md) separates actual byte evidence and RPM measurements from these state-machine hypotheses, and lists unresolved code paths.

## 5. Why checksums became part of the story

The **original** MIN54-QUIET achieved its acoustic goal but exhibited a serious **AC/S5 fault**: plugging in a charger while the laptop was shut down could produce maximum fan speed and an unresponsive power button. MIN54 (only the two *Minimum Drive* bytes) and 66-QUIET (only the five table bytes) produced similar incidents, despite having **disjoint sets of functional changes**.

We discovered that stock A14 has three separately zero-balanced regions of 32-bit little-endian words:

| Working region name | EC half-open byte interval | Compensation word |
|---|---|---|
| BOOT-1 | \`[0x1000,0x4400)\` | **\`0x43FC\`** |
| BRIDGE | \`[0x4400,0x5000)\` | \`0x4FFC\` |
| BOOT-2 | \`[0x5000,0x38000)\` | **\`0x37FFC\`** |

The historical MIN54-QUIET violated BOOT-1 and BOOT-2 checksums. The **M54FIX** update preserved exactly the seven functional fan-control edits while restoring all three regions to a zero sum by changing **four checksum-compensation bytes**:

\`\`\`text
BOOT-1 @ 0x43FC: 0x2704FF56 → 0x2704FF68
BOOT-2 @ 0x37FFC: 0xC86347B3 → 0xCD8945B3
BRIDGE: unchanged
\`\`\`

The corrected updater passed two offline validation rounds, successfully booted the test laptop after FreeDOS flashing, and was followed by **one user-reported successful AC insertion in S5**. This strongly supports missing internal checksum compensation as the earlier defect, **but does not prove the exact ARC600 fallback path or long-term safety**. No independent physical EC-flash readback or verified recovery method is available.

Read the [M54FIX case study](docs/M54FIX_AC_S5_CASE_STUDY.md) and the [additive checksum investigation](docs/EC_ADDITIVE_CHECKSUM.md) for exact per-byte changes, image hashes, mathematical checks and limitations.

## 6. Technical documentation and source code

- [**M54FIX case study**](docs/M54FIX_AC_S5_CASE_STUDY.md) — experiments, all 11 changed EC bytes, exact hashes, test observations and limitations.
- [Three additive EC checksum regions](docs/EC_ADDITIVE_CHECKSUM.md) — how the format was discovered and why the first whole-image sum hypothesis required correction.
- [The original AC/S5 incident](docs/AC_S5_POSTMORTEM.md) — October 19 observations and the subsequent explanation.
- [ARC600 side findings and dead ends](docs/EC_ARC600_SIDE_FINDINGS.md) — boot code, timers, interrupts, indexed fan MMIO, TACH, flash records, service commands and keyboard decoding.
- [Historical thermal test results](docs/HISTORICAL_THERMAL_RESULTS.md) — 2,500 / 3,300 / 4,300 RPM curve and nine-minute tests on the uncorrected image.
- [Read-only UEFI/PE static reproduction](docs/REPRODUCE.md).
- [Offline checksum auditor and historical builder](docs/TOOLS.md).

The side-findings document preserves the important results of a multi-day deep dive. The large original notebooks and terminal transcripts are not included in this privacy-minimized English edition; their absence must not be confused with independent reproduction of every discovered execution path.

## 7. Exact image identifiers (SHA-256)

```text
Stock A14 EC     dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96
MIN54-QUIET EC   b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab
M54FIX EC        90648894233eca7b25ee2fc53922254988c7a764e7f582c429ee34f175e59fb8
M54FIX EXE       45a735456487f09f94043c2405ef4df9bc4a84db4e8e5a05bd814572e5fa9f40
```

## 8. Open licenses — free to reuse

**Please use, improve, translate and share this work. Commercial use is allowed.**

- **Python source code in `tools/`: [MIT License](LICENSE)** ([SPDX: MIT](https://spdx.org/licenses/MIT)). Copy, modify, redistribute, sublicense, or use the tools commercially, retaining the copyright and license notice.
- **Original research documentation: [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE-DOCS.md)** ([license overview](https://creativecommons.org/licenses/by/4.0/)). Copy, redistribute, translate, adapt, or use the writing commercially, crediting **peter3332**, linking to the license, and indicating any changes.

The grants cover material we are entitled to license; **third-party content and Dell firmware are not relicensed**. See [documentation-license details](LICENSE-DOCS.md).

## 9. Reproduction and safety

The `tools/` directory contains only **Python source**, with no Dell-owned binary files. `audit_ec_additive_checksum.py` is read-only. `build_min54quiet_from_available.py` can reconstruct an **unsigned, modified updater file on disk** from verified inputs supplied separately by a researcher; **it does not flash** the laptop.

A rebuilt EXE **does not possess a valid Dell Authenticode signature**. Flashing nonstandard EC firmware can irreversibly damage the laptop; this publication is **technical research, not a recommendation to perform a flash or force manual fan control**.

**Scope:** one physical E5420 with Dell BIOS A14; measured RPM/temperature under limited conditions, one user-reported successful AC/S5 attempt after the checksum repair, and no physical EC flash readback or validated recovery path.

## 10. Privacy and provenance

This public edition was published as a **separate Git repository with clean history**. It intentionally excludes raw terminal logs, local user/hostname strings, personal correspondence, prepublication commit history, proprietary firmware and generated updater executables. The full original research archive remains separate and private.

For background, safety, and public-release provenance, see [PUBLICATION.md](PUBLICATION.md). The specific borrowed code credits described in the original private research are not incorporated into this source-only release.
