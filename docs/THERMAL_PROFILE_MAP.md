# Dell Latitude E5420 A14 — fan Minimum Drive, thermal profile tables, and hysteresis

**Research dates:** October 11–24, 2026  
**Scope:** one Dell Latitude E5420 with the stock A14-derived EC image (`0x38000` bytes). Offsets are **raw EC image file offsets**, not host physical memory addresses or PFS-container offsets.  
**Evidence:** static ARC600 disassembly, byte-level comparisons of image variants, and short on-device `dell_smm` RPM/temperature measurements. The original full notebook and raw logs remain outside this public, privacy-minimized edition.

> **Key distinction:** the byte layout and the edited RPM values are directly established; the idea that each thermal row contains *down/up hysteresis thresholds* is a **strong, behavior-consistent interpretation**, **not** a formally traced implementation of the EC state machine. Neither thermal testing nor fan-curve edits alone validate AC/S5 firmware integrity. See the [M54FIX case study](M54FIX_AC_S5_CASE_STUDY.md).

## 1. Where the fan Minimum Drive parameter is initialized

Two separate ARC600 startup paths load the same parameter value before calling an indexed MMIO helper:

| Code path (factory A14 EC) | Index operand | Value byte offset | Stock value | Quiet/M54FIX value |
|---|---:|---:|---:|---:|
| Around `0x2748` → wrapper `0x1474` → helper `0x1DC4` | `0x87` | **`0x02750`** | `0x66` | `0x54` |
| Around `0x164CE` → wrapper `0x5784` → helper `0x11488` | `0x87` | **`0x164D6`** | `0x66` | `0x54` |

Both paths supply the base **`0xF01480`**. The examined helpers write the register **index** to `[base+4]` = `0xF01484`, and its **value** to `[base+8]` = `0xF01488`. A BUSY/status bit is polled with a bounded loop (maximum **1,024** checks); an additional error-recovery helper was also observed.

The values `0x19`, `0x10`, `0x66`, `0xF5` appear alongside consecutive indices `0x85`, `0x86`, `0x87`, `0x88`. They resemble the **Spin Up**, **Max Step**, **Minimum Drive**, and **Valid TACH** configuration fields of other SMSC/Microchip fan-control hardware. Consequently **`0x87 = Minimum Drive` is an evidence-supported interpretation**, not a vendor-confirmed register definition for the E5420's exact EC silicon.

**It is not a direct RPM setpoint.** Lowering this value affects the minimum attainable drive in RPM control; the observed physical speed also depends on the SMM target, tachometer feedback, fan mechanics, and startup logic. The tempting interpretation of stock `0x66` as “40% PWM” is only an analogy to an external component's 8-bit setting; the live electrical PWM duty on this laptop was **not measured**.

### Historical progression of Minimum Drive tests

The two code operands were altered together in each variant. Measurements below refer to **manual Dell SMM RPM requests** rather than automatic thermal stages:

| Test image | Both operands | Manual RPM request | Reported settled fan behavior |
|---|---|---|---|
| Stock A14 | `0x66` | 2,000 RPM | ~2,725 RPM |
| MIN60 | `0x60` | 2,000 RPM | ~2,575–2,581 RPM |
| MIN58 | `0x58` | 1,500 RPM after spin-up | ~2,368–2,377 RPM (mean/median ~2,373) |
| MIN54 | `0x54` | 1,500 RPM | ~2,263–2,270 RPM (mean ~2,267) |
| MIN50 | `0x50` | 1,500 or 2,000 RPM | Unstable oscillations, not a viable quiet floor |

MIN54 achieved **five successful starts from a stopped fan** in one short series; fan speed settled around **2,258–2,266 RPM** following a transient boost near **3,153–3,191 RPM**. That is *limited evidence of repeatable start-up behavior*, not a guarantee for prolonged use or every power state. MIN50 could also stabilize at a **higher** requested target (~2,250 RPM): its instability was request-dependent, not a universal inability to spin at a particular speed.

The MIN54-AUTO image later patched the **first BIOS-controlled fan-table speed**, unlike the earlier Minimum Drive-only experiments. This distinction is essential: reducing the drive floor by itself did **not** change the stock automatic first-stage target (~3,300 RPM).

## 2. Thermally controlled fan-profile data layout

Three consecutive 32-bit **little-endian pointer values** in the extracted EC image point at three candidate thermal profile records. The actual pointer operands are reported as image-offset targets; they are not confirmed CPU MMIO addresses.

| Pointer stored at | Points to | Header begins at | First 4-byte stage at | Interpretation |
|---|---|---|---|---|
| **`0x216B8`** | **`0x216C8`** | `0x216C8` | **`0x216D0`** | **Profile A**, very likely CPU-related |
| **`0x216BC`** | **`0x216EC`** | `0x216EC` | **`0x216F4`** | **Profile B**, sensor not mapped |
| **`0x216C0`** | **`0x21710`** | `0x21710` | **`0x21718`** | **Profile C**, sensor not mapped |

Each candidate profile occupies **`0x24` = 36 bytes**. The observed first stage follows an **8-byte preamble**, and the first three stage entries are **4 bytes each**. For profile A, the four bytes beginning at `0x216CC` are:

```text
81 43 00 00
   ^^
   0x43 = 67 decimal
```

In short BIOS AUTO tests the fan started around **67°C according to Dell's CPU sensor**, making `0x43` a plausible fan-on threshold or related setting. The meaning of the first byte `0x81` and other preamble bytes remains **unresolved**. There is no confirmed direct little-endian xref to the pointer table from the earlier static-search pass; the code may obtain the table indirectly.

### Profile A — likely CPU (three known normal entries)

| Stage entry begins at | First temperature byte | Second temperature byte | Stock target | M54FIX target |
|---|---:|---:|---:|---:|
| **`0x216D0`** | **50°C** (`0x32`) | **72°C** (`0x48`) | 3,300 RPM | **2,500 RPM** |
| **`0x216D4`** | **65°C** (`0x41`) | **78°C stock / 80°C M54FIX** (`0x4E → 0x50`) | 3,800 RPM | **3,300 RPM** |
| **`0x216D8`** | **74°C** (`0x4A`) | **85°C** (`0x55`) | 4,300 RPM | **4,300 RPM (unchanged)** |

The literal three-entry bytes in **M54FIX** are verified as:

```text
EC+0x216D0:
32 48 C4 09 | 41 50 E4 0C | 4A 55 CC 10
|temp| RPM  | |temp| RPM  | |temp| RPM  |
 50  72 2500   65  80 3300   74  85 4300
```

Here `C4 09` means `0x09C4 = 2500` in little-endian, `E4 0C` means `0x0CE4 = 3300`, and `CC 10` means `0x10CC = 4300`.

The **original stock** first three entries, before the selected quiet-curve patch, were:

```text
32 48 E4 0C | 41 4E D8 0E | 4A 55 CC 10
 50  72 3300   65  78 3800   74  85 4300
```

Only these **three normal stage entries** have been listed in the concise public edition. The full `0x24`-byte records may also contain special/fail-safe fields; the value **`0x5356`** was seen in the original research and **must not be interpreted as an ordinary 21,334 RPM fan setpoint**. Do not assume the entire profile beyond these entries has been semantically decoded.

### Profile B — not yet assigned to a physical sensor

| Stage entry at | First temp | Second temp | Stock / M54FIX target |
|---|---:|---:|---:|
| **`0x216F4`** | 43°C | 50°C | **3,300 RPM** |
| **`0x216F8`** | 47°C | 54°C | **3,800 RPM** |
| **`0x216FC`** | 51°C | 58°C | **4,300 RPM** |

### Profile C — not yet assigned to a physical sensor

| Stage entry at | First temp | Second temp | Stock / M54FIX target |
|---|---:|---:|---:|
| **`0x21718`** | 48°C | 53°C | **3,300 RPM** |
| **`0x2171C`** | 51°C | 56°C | **3,800 RPM** |
| **`0x21720`** | 54°C | 59°C | **4,300 RPM** |

Profiles B and C were *not modified* in the quiet-fan experiment, so their listed values are the **same in stock A14 and M54FIX**. Values come from the previously documented extracted data; their physical association with Ambient, SODIMM, chipset, GPU, or other temperature sources remains **unestablished**.

## 3. Hysteresis: likely behavior, not proven instruction semantics

Each normal stage entry holds a **lower** and **upper** temperature byte next to a 16-bit little-endian RPM target. A natural working model is that the *upper* threshold controls escalation **from** the current stage when heating, while a lower threshold controls de-escalation when cooling. A fan controller retaining its previous state this way avoids repeated switching near one temperature threshold.

For the **M54FIX profile A**, that model predicts:

| State transition (proposed) | Increasing temperature | Decreasing temperature | Nominal gap |
|---|---:|---:|---:|
| Fan OFF ↔ first stage (2,500 RPM) | Near **67°C**, inferred from `0x216CC = 0x43` and starts seen in testing | Near **50°C** (first stage's lower byte) | ~17°C, with a different on threshold source |
| First stage ↔ second stage (2,500 ↔ 3,300 RPM) | Near **72°C** (upper byte of first entry) | Potentially near **65°C** (lower byte of second entry) | **7°C** |
| Second stage ↔ third stage (3,300 ↔ 4,300 RPM) | Near **80°C** (M54FIX upper byte of second entry) | Potentially near **74°C** (lower byte of third entry) | **6°C** |

**What the tests actually support:**

- In the two historical QUIET/QUIET2 variants, modifying `0x216D1` from `0x48 = 72` to `0x4A = 74` coincided with the observed first→second transition moving from about **72°C** to about **74°C** on the Dell CPU sensor, under similar workloads.
- A historical short all-core QUIET run showed escalation to about **4,300 RPM** as Dell CPU temperature reached roughly **80–81°C**, consistent with the second entry's 80°C upper byte.
- During cooling, the fan returned to first-stage speed and later stopped around **50°C** on the Dell CPU sensor, consistent with the first entry's lower byte.
- Other historical BIOS AUTO tests showed a fan-start event near **67°C** on the same Dell-reported sensor, consistent with the profile A header's `0x43`.

**What remains unproven:**

- No complete ARC600 code path has been shown comparing *both* bytes against a calibrated Dell CPU sensor and updating the current fan-stage state.
- The proposed **65°C and 74°C decreasing-transition thresholds** were not isolated by controlled tests showing the precise stage-change temperature. These are inferred from byte pairs, not independently measured switch-back points.
- We have not established whether there are sampling delays, temperature filtering/averaging, separate startup hysteresis, time dwell, per-zone maximum arbitration, or different behavior with multiple hot sensors.
- BIOS- or EC-level fan management may combine several thermal profiles, potentially overriding the CPU-related profile A when other zones become hot.

The above thresholds therefore **describe a highly plausible hysteretic table structure**, not a guaranteed transition-state algorithm. Do not infer a universal rule such as “the fan is always stage 2 exactly between 72 and 80°C” without regard to its previous state and other thermal zones.

## 4. Firmware editions and exact changes relevant to these tables

| Edition | Minimum Drive operands | First stage A | Second stage A | Other profiles |
|---|---|---:|---:|---|
| **Factory A14** | both `0x66` | 3,300 RPM | 3,800 RPM | Stock |
| **MIN54** | both `0x54` | 3,300 RPM | 3,800 RPM | Stock |
| **MIN54-AUTO** | both `0x54` | **2,260 RPM** | 3,800 RPM | Stock |
| **MIN54-QUIET** (old, **checksum-invalid**) | both `0x54` | **2,500 RPM** | **3,300 RPM** | Stock |
| **M54FIX** (checksum-corrected) | both `0x54` | **2,500 RPM** | **3,300 RPM** | Stock |

The third stage remains **4,300 RPM**. MIN54-QUIET also changed the **second entry's upper temperature byte from 78°C to 80°C**, and M54FIX retained that change.

**CRITICAL:** the uncorrected firmware variants violated one or more additive EC checksum invariants, and were associated with a serious AC/S5 failure. **Copying fan-table bytes alone is not sufficient to produce an internally valid image.** See the [three-region checksum analysis](EC_ADDITIVE_CHECKSUM.md) and the [M54FIX case study](M54FIX_AC_S5_CASE_STUDY.md). Successful checksum arithmetic or offline repackaging does **not** guarantee flashing safety or device recovery.

## 5. Useful unresolved questions

1. Find and disassemble the routine(s) reading the pointer table `0x216B8..0x216C0` and compare logic for both temperature bytes.
2. Identify how a profile header such as `0x81 0x43 0x00 0x00` is used, especially whether `0x43` is truly an on threshold.
3. Establish the sensor-to-profile assignment for B/C with dataflow or carefully scoped, read-only correlations.
4. Explain additional entries and any special value `0x5356` without treating every 16-bit field as RPM.
5. Understand arbitration across profiles, fault fallback and AC/S5 power-state execution without additional blind flashing experiments.

**Safety:** this is a research map for one firmware build, not a fan-curve tuning recommendation, instruction to flash a modified EXE, or a substitute for a tested EC recovery procedure. Documentation is licensed under [CC BY 4.0](../LICENSE-DOCS.md). The two offline Python tools are under [MIT](../LICENSE).
