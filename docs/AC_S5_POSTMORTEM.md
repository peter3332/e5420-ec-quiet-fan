# Dell Latitude E5420 A14 — original AC/S5 incident postmortem (October 19, 2026)

> **Public research edition.** This is a self-contained English technical analysis distilled from a larger private research archive. Detailed original-language notebooks and raw terminal dumps are intentionally not included to protect local identifiers and private Git history. Technical claims distinguish observed machine-code behavior from inference and open questions.

> **Historical document, with later findings.** This is the English edition of the original Polish postmortem. It preserves the chronology and the uncertainties recorded **before** the three additive EC checksum regions and M54FIX were identified on October 24. Subsequent experiments with MIN54 and 66-QUIET also failed despite disjoint sets of modified fan-control bytes. M54FIX later had **one user-reported successful AC insertion in S5**; see the [M54FIX case study](M54FIX_AC_S5_CASE_STUDY.md) and [three-region checksum analysis](EC_ADDITIVE_CHECKSUM.md).

> **Safety warning as of the original incident.** The historical claim that MIN54-QUIET was a fully successful solution on October 13 was withdrawn after a serious EC/power malfunction on October 19. The factory A14 updater restored normal behavior. Historical fan/thermal tests do not validate all ACPI states, and there is no independently validated recovery mechanism for a corrupted EC. Do not use these notes as a firmware-flashing procedure.

## 1. Direct observations on the physical laptop

Device: one Dell Latitude E5420, Dell BIOS A14.

- With experimental **MIN54-QUIET** installed, plugging the AC adapter into a **powered-off (S5)** laptop made the fan run at very high speed, apparently near 100%, while the power button stopped responding normally and the EC appeared stuck. The behavior was reported with and without the battery installed, using two genuine Dell AC adapters.
- In some subsequent battery-only starts, POST reported an unset Service Tag or an unidentified AC adapter type/rating. A following restart could clear the warning. This does **not** imply the physical tag was permanently erased.
- Several previous successful flashes and thermal tests had been done with AC **already connected**. Those tests **did not exercise insertion of AC in S5**.
- Before the factory restore, if BIOS Setup was opened while on battery and the AC adapter was subsequently connected, BIOS Setup showed **AC Adapter 130 W**, battery **100%**, and **Health Normal**. That is compatible with a fault specific to another power-state transition.
- On **October 19, 2026**, the experimenter flashed the original Dell A14 package and reported that connecting AC no longer triggered the problem. Neither the adapter nor DC-in connector was replaced.

**Inference at that date:** the before/after comparison strongly associated the fault with experimental EC firmware or with the flashing/reset state of the EC, not with a proven physical defect in the power adapter or DC jack. A factory reflash can change both code and persistent controller state; it does not identify a particular faulty instruction.

## 2. Independent comparison of the two real updater EXEs

The offline archive `e5420-A14-vs-MIN54Q.zip` supplied actual full updater files: `ORIGINAL-A14.exe` (Dell stock) and `MIN54-QUIET.exe` (a copy of the `M54Q.EXE` tested from FreeDOS). Their SHA-256 values matched earlier project records.

| Item | Stock A14 | MIN54-QUIET |
|---|---|---|
| Updater EXE SHA-256 | `8fef5ea2dbaac0dd91b9b11663e4cf2eacfc86c50bec7db4a62a5b4d36ef0d1e` | `b69263839c45631b2d67ac013769e2afc3af86d96f9c93177846ffa4bcb72a99` |
| EXE size | 3,082,144 bytes | 3,082,144 bytes |
| Uncompressed PFS | 5,959,851 bytes | 5,959,851 bytes |
| Uncompressed PFS SHA-256 | `8189811e2277fe8c883370fa0f199a3e17311023d588a688811e42fcedadb585` | `e839f0eb7e9ef6a2c7af5afc102f16f362e4ab2e70778e1c4f40f5ea73464c34` |
| Extracted EC SHA-256 | `dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96` | `b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab` |

**Exact binary differences:**

- **System BIOS:** 4,194,304 bytes (`0x400000`) at PFS offset `0x58`; **zero changed bytes**. Both BIOS blobs had SHA-256 `f39210d88d4b0170b9478eb3dd76e0b7f6d9c84d73a5e4a7eff14bec9df04a37`.
- **EC:** 229,376 bytes (`0x38000`) at PFS offset `0x400510`; **exactly seven changed bytes**, shown below.
- **Complete uncompressed PFS:** **14 changed bytes** — seven EC bytes, four EC CRC bytes, and three bytes of the four-byte PFS CRC field that actually differed.
- **Inverted EC CRC32:** stock `0xC15A8B75`, patched `0x2434273E`; **PFS CRC:** stock `0x6E7861CC`, patched `0x4C728ACC`. Stored and independently calculated values matched.
- **Compressed PFS:** stock 2,660,733 bytes, patched 2,660,734 bytes. Recompression produced large numbers of EXE-level byte changes (historically 713,306), which should **not** be mistaken for additional differences in the extracted BIOS or EC payload.
- The PFS/PE wrapper and checksum were structurally consistent. The historical executable retained the original certificate area, but **Dell's cryptographic signature does not authenticate the patched EXE**.
- **No physical readback of EC flash after flashing was performed.** Comparisons verify updater input files, not the exact bytes resident in the EC during the failure.

The **seven** modified EC bytes at that stage:

| Raw EC offset | Factory → MIN54-QUIET | Interpretation |
|---|---|---|
| `0x02750` | `66 → 54` | ARC instruction operand for indexed `0x87` ("Minimum Drive") |
| `0x164D6` | `66 → 54` | Second similar initialization path |
| `0x216D2` | `E4 → C4` | First speed low byte |
| `0x216D3` | `0C → 09` | First stage 3300 → 2500 RPM, high byte |
| `0x216D5` | `4E → 50` | Temperature threshold 78 → 80°C |
| `0x216D6` | `D8 → E4` | Second speed low byte |
| `0x216D7` | `0E → 0C` | Second stage 3800 → 3300 RPM, high byte |

## 3. Why did we patch 0x66, and why in two locations?

The early October investigation treated the EC image as actual **ARC600 machine code**, rather than randomly editing hex patterns.

Two analogous sequences were found:

```text
around EC 0x2748:
    mov_s r0,0xF01480
    mov_s r1,0x87
    mov_s r2,0x66
    bl    0x1474
    operand 0x66 at 0x2750

around EC 0x164CE:
    mov_s r0,0xF01480
    mov_s r1,0x87
    mov_s r2,0x66
    bl    0x5784
    operand 0x66 at 0x164D6
```

Further disassembly established that the call wrappers ultimately write **index `0x87` to `[0xF01480+4]`** and **value `0x66` to `[0xF01480+8]`**. This is an **indexed hardware interface**; the precise silicon identity was not established from the code alone.

Both configuration blocks also contained the characteristic cluster `0x85=0x19`, `0x86=0x10`, `0x87=0x66`, `0x88=0xF5`. This pattern resembles fields named **Spin Up, Max Step, Minimum Drive, Valid TACH** in the [SMSC EMC2305](https://www.alldatasheet.com/html-pdf/858152/SMSC/EMC2305-1-AP-TR/4834/44/EMC2305-1-AP-TR.html) datasheet. The [MEC170x](https://ww1.microchip.com/downloads/en/DeviceDoc/00002206C.pdf) documentation contains related RPM2PWM concepts, but with a different processor and register map. These are **analogies**, not a verified physical register map of this laptop.

A search of the factory EC found the relevant instruction-byte pattern exactly twice. The two operands were patched together to avoid leaving another initialization path that would still write `0x66`. We **did not know** which power states executed each path or whether they target one hardware block.

Earlier observations:
- MIN60 (`0x66→0x60`): a manual 2000-RPM SMM request resulted in about **2575–2581 RPM**, vs approximately **2725 RPM** on stock.
- MIN58 and MIN54 further lowered the observed floor.
- MIN50 produced instability.
- MIN54 seemed a useful practical compromise during the limited boot and thermal tests.

These tests established a **correlation between the patched parameter and RPM**, not complete fan-system safety or stable AC/S5 behavior.

Historical references: Minimum Drive origin, MIN60 result, MIN54 result, quiet profile testing.

## 4. Original competing failure hypotheses — historical, not final explanations

1. **The `0x66→0x54` initialization change:** a reasonable first suspect, especially if another power state used a different initialization path. **Not demonstrated.**
2. The five table modifications, or their interaction with the Minimum Drive edits, or a different instance of similar fan hardware.
3. A change in persistent EC/NVRAM state, reset sequencing, or updater side effects. A stock update could repair code and/or internal state.
4. Independent adapter/DC hardware trouble could not be excluded absolutely, but was less consistent with the outcome of the stock restore without changing any hardware.

**Do not say that the `0x54` operand was proven to cause the failure.** No S5 instruction trace, full hardware schematic, or readback was available. Equally, restoring factory firmware does not establish that the updater rewrote every EC flash block.

## 5. Implications for the fan-noise project

The existing RPM and temperature numbers were legitimate observations **under the specific test conditions**. They were not a certification of firmware behavior over all EC power states. The October 13 claim that the quiet build was a finished, generally safe solution was **withdrawn** after the incident on October 19.

The original postmortem recommended no further experimental flashing. The complete range of power-state checks would have to include, at minimum: AC insertion while in S5, battery-only boot, AC loss/reconnection, sleep/resume, sensor faults, fan tachometer failures, thermal extremes, and a realistic independent EC recovery mechanism. **A checklist alone does not make further flashing safe.**

This incident exposed a validation-scope mistake: recognizing a likely Minimum Drive field and observing RPM effects did not justify assuming the firmware was safe under all power scenarios.

## 6. Later October 24 addendum: disjoint patches and additive sums

After MIN54 and 66-QUIET also showed an AC/S5 fault, the `0x54`-specific theory became much weaker: MIN54 modified only `0x2750` and `0x164D6`; 66-QUIET modified only `0x216D2/3/5/6/7`. Both were associated with the same class of failure. Correct PFS and PE checksums were therefore insufficient evidence of a valid EC image.

A newly discovered property of stock EC A14 was that **the 32-bit little-endian additive word sum of `EC[0x1000:0x38000]` equaled zero**. The last word at `0x37FFC` was `0xC86347B3`; the sum of preceding words was `0x379CB84D`.

| Image | Historical combined-region sum |
|---|---|
| Stock A14 | `0x00000000` |
| MIN54 | `0xFFEDFFEE` |
| MIN54-QUIET | `0xFADA01EE` |
| 66-QUIET | `0xFAEC0200` |

Later in the same investigation the combined interval was recognized as **three separately zero-balanced regions** with compensation words at `0x43FC`, `0x4FFC`, and `0x37FFC`. The exact breakdown is in the [English checksum analysis](EC_ADDITIVE_CHECKSUM.md). The originally suspected validator had not yet been proven as a runtime AC/S5 trace.

**Subsequent outcome:** the M54FIX image corrected BOOT-1 and BOOT-2 compensation words, preserving all seven functional changes from the original MIN54-QUIET. FreeDOS flashing and Xubuntu boot succeeded; the fan behavior was observed and a user-reported AC/S5 insertion succeeded once. See the [M54FIX report](M54FIX_AC_S5_CASE_STUDY.md). The success is an important experimental update, not permission to erase the old postmortem or assume long-term safety.

## 7. Provenance and limits

This record derives from the original project notebooks, independently compared updater files, and the user's October 19 incident observations; its addendum is based on the later October 24 research. The original investigation did not involve a hardware flash readback or an independently verified recovery process. This document **does not distribute Dell firmware** and **does not instruct the reader to flash a patched updater**.
