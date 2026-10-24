# Dell Latitude E5420 A14: M54FIX — an EC AC/S5 failure and the missing checksums

> **Public research edition.** This is a self-contained English technical analysis distilled from a larger private research archive. Detailed original-language notebooks and raw terminal dumps are intentionally not included to protect local identifiers and private Git history. Technical claims distinguish observed machine-code behavior from inference and open questions.

**Investigation and hardware observations:** October 24, 2026  
**Device:** one Dell Latitude E5420, BIOS A14, EC code targeting ARC600, Xubuntu Linux  
**Status:** a user-reported successful experimental repair, not full reliability qualification or a general-purpose flash procedure.

> **Main result.** M54FIX preserves the exact **seven functional changes** of the historical MIN54-QUIET fan profile and adds correction of the internal additive checksum words in two EC regions. It was flashed from FreeDOS, booted Xubuntu successfully, produced the intended approximately 2,500 RPM fan stage and successfully entered a stopped-fan state after the BIOS-auto command. The experimenter additionally reported a **successful AC-plugging event with the laptop powered off (S5)**, the scenario that had previously triggered a stuck EC and maximum-speed fan operation. This observation strongly supports the checksum hypothesis, but we lack a full multi-cycle protocol, an independent physical flash readback, and a verified EC recovery method.

## 1. The project was about noise, not firmware for its own sake

The owner wanted to make an otherwise serviceable Dell Latitude E5420 quieter during light use. Its stock low fan stage ran at roughly **3,300 RPM** and was distractingly audible. The design goal was to reduce that stage to approximately **2,500 RPM**, while keeping higher stages and thermal safeguards available.

The historical MIN54-QUIET implementation used a profile with **2,500 / 3,300 / 4,300 RPM** and changed **Minimum Drive** from `0x66` to `0x54` in two initialization paths. A nine-minute BIOS-auto thermal test on October 13 was completed below the selected 85°C cutoff (highest observed core temperature approximately 83°C). These historical measurements must **not** be mistaken for a full thermal qualification of the later M54FIX binary.

A severe, unexpected issue then emerged: plugging the AC adapter into the *shut-down* computer could make the fan run near maximum speed, leave the power button unresponsive, and put the EC into a state from which normal software control did not recover. Restoring factory Dell A14 removed the symptom. Earlier Linux boots, fan measurements, and thermal tests had **not exercised that specific AC/S5 transition**.

Crucially, the same class of failure was subsequently reported for two smaller patches:
- **MIN54** changed only the two Minimum Drive locations.
- **66-QUIET** retained stock Minimum Drive but changed five bytes of the fan-profile table.

Because the *functional* changed-byte sets of those two variants did not overlap, no single modified fan operand could explain all incidents. The analysis turned toward integrity of the EC firmware image itself.

## 2. Three independent additive checksums in the EC image

The extracted EC payload is **`0x38000` = 229,376 bytes**. The stock A14 image has **three independently zero-balanced regions** when interpreted as little-endian unsigned 32-bit words summed modulo `2^32`:

| Working name | Byte range [start, end) | Compensation word at | Original stored DWORD |
|---|---|---|---|
| BOOT-1 | `0x1000 .. 0x4400` | `0x43FC` | `0x2704FF56` |
| BRIDGE | `0x4400 .. 0x5000` | `0x4FFC` | `0x2093D4E7` |
| BOOT-2 | `0x5000 .. 0x38000` | `0x37FFC` | `0xC86347B3` |

All three region names are our **working labels**, not official Microchip or Dell names. The boundaries are supported by separate vector/entry structures beginning at `0x4400` and `0x5000`.

The defining property is:

```text
sum(uint32_le(region[0:4]), uint32_le(region[4:8]), ...)
    & 0xffffffff == 0

new_compensation_dword = (old_compensation_dword - bad_region_sum)
    & 0xffffffff
```

This is **not CRC32**. The PE checksum, Dell PFS CRC, and these internal EC word sums are different layers of integrity verification. A combined zero sum over `[0x1000, 0x38000)` is mathematically consistent with the three separately balanced regions, but does not by itself reveal those boundaries.

### Observed checksum residuals

| Region | Historical MIN54-QUIET | M54FIX |
|---|---|---|
| BOOT-1 | `0xFFFFFFEE` | `0x00000000` |
| BRIDGE | `0x00000000` | `0x00000000` |
| BOOT-2 | `0xFADA0200` | `0x00000000` |

The precise compensation edits were:

```text
BOOT-1 @ 0x43FC: 0x2704FF56 → 0x2704FF68  (one changed byte)
BOOT-2 @ 0x37FFC: 0xC86347B3 → 0xCD8945B3  (three changed bytes)
BRIDGE @ 0x4FFC: unchanged
```

All three previously malfunctioning versions violated the BOOT-2 zero-sum condition. MIN54 and MIN54-QUIET additionally violated BOOT-1; 66-QUIET did not. Because **both** faulty regions were corrected together in M54FIX, the positive test does **not** independently establish whether both corrections were necessary.

## 3. Exactly which EC bytes changed?

Against stock Dell A14, the final corrected image differs at **11 byte offsets**. Seven are the previously tested functional changes, and four are compensation bytes. Nothing else in the EC payload was intentionally altered:

| Raw EC offset | Stock byte → M54FIX byte | Interpretation |
|---|---|---|
| `0x02750` | `66 → 54` | Minimum Drive operand, first path |
| `0x043FC` | `56 → 68` | BOOT-1 compensation |
| `0x164D6` | `66 → 54` | Minimum Drive operand, second path |
| `0x216D2` | `E4 → C4` | First speed: 3300 → 2500 RPM, low byte |
| `0x216D3` | `0C → 09` | First speed: high byte |
| `0x216D5` | `4E → 50` | Second profile entry's threshold byte: 78 → 80 |
| `0x216D6` | `D8 → E4` | Second speed: 3800 → 3300 RPM, low byte |
| `0x216D7` | `0E → 0C` | Second speed: high byte |
| `0x37FFD` | `47 → 45` | BOOT-2 compensation |
| `0x37FFE` | `63 → 89` | BOOT-2 compensation |
| `0x37FFF` | `C8 → CD` | BOOT-2 compensation |

The first three entries in the CPU-related profile A at offset `0x216D0` are:

```text
32 48 C4 09 | 41 50 E4 0C | 4A 55 CC 10
50 72 2500  | 65 80 3300  | 74 85 4300
```

The interpretation of the associated temperature thresholds is supported by empirical tests, but we are not claiming a complete vendor-level formal proof of every table field.

**Difference from historical MIN54-QUIET:** only the four compensation bytes at `0x43FC`, `0x37FFD`, `0x37FFE`, and `0x37FFF`. The functional fan-control payload was left byte-identical.

## 4. Cryptographic file identities

The following SHA-256 values identify **exact full files**, avoiding ambiguity between historical builds:

| Image | SHA-256 |
|---|---|
| Stock A14 EC | `dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96` |
| Historical MIN54-QUIET EC | `b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab` |
| **M54FIX EC** | **`90648894233eca7b25ee2fc53922254988c7a764e7f582c429ee34f175e59fb8`** |
| **M54FIX updater EXE** | **`45a735456487f09f94043c2405ef4df9bc4a84db4e8e5a05bd814572e5fa9f40`** |

The local offline output files were:

```text
work/EC-MIN54QUIET-CHECKSUMMED.bin
work/E5420A14-min54quiet-CHECKSUMMED-UNSIGNED.exe
```

The latter updater was named `M54FIX.EXE` on the FreeDOS USB stick.

## 5. Build verification: what was actually checked?

The exact reconstruction script used for the successful experiment is archived as [`tools/build_min54quiet_from_available.py`](../tools/build_min54quiet_from_available.py). It is a Python-standard-library **offline builder** and does not interact with the live EC.

Its workflow:

1. Verify the SHA-256 identities of the stock EXE and extracted EC inputs.
2. Reconstruct the historical MIN54-QUIET EC and verify the **known historical SHA-256 before modifying the checksum words**.
3. Correct the two compensation DWORDs and verify each of the three separate additive region sums.
4. Insert the modified EC into the Dell PFS payload, recomputing the EC CRC, PFS CRC, and outer PE checksum.
5. Re-extract the EC from the finished EXE and check that its bytes match the separately produced BIN.
6. Refuse unexpected bytes, inconsistent hashes, or overwriting existing files.

An independent second offline audit on the Latitude rechecked both CRCs, all three additive sums, the exact stock-to-M54FIX changed-offset set, and byte identity between the EC extracted from the final EXE and the standalone final BIN. Its final report was **`AUDYT ZAKONCZONY POMYSLNIE`** (“AUDIT COMPLETED SUCCESSFULLY”).

The independent BIOSUtilities parser was **not** used for this final file on that machine.

### Offline reproduction only

Using your own, independently authenticated stock input files:

```bash
cd ~/e5420-ec
# Requires firmware/E5420A14.exe and work/stock-EC-A14.bin
python3 tools/build_min54quiet_from_available.py
sha256sum work/EC-MIN54QUIET-CHECKSUMMED.bin \
          work/E5420A14-min54quiet-CHECKSUMMED-UNSIGNED.exe
```

These commands prepare and verify files **on disk**. They do not constitute a recommendation to flash the result. The reconstructed updater retains the historical packaging structure but its **Dell Authenticode signature is invalid for the modified bytes**. Correcting CRC or PE checksums is **not** equivalent to a valid vendor signature. No firmware files or rebuilt EXE are included in this repository.

## 6. Hardware observations on October 24, 2026

**Reported results on the physical test device:**

- Flashing `M54FIX.EXE` under FreeDOS: **reported successful**.
- Starting Xubuntu: **successful**.
- The first fan stage remained at approximately **2,512–2,533 RPM** while the Dell-reported CPU temperature was around **55–64°C** and `coretemp` reported roughly **56–67°C**.
- The `dell_smm_hwmon` driver initially showed `pwm1_enable=1` and `MANUAL CONTROL`. Writing `2` to `pwm1_enable` returned **`EINVAL`** and therefore did *not* verify a successful switch to AUTO.
- After building `TomFreudenberg/dell-bios-fan-control` and issuing its enable command `sudo dell-bios-fan-control 1` (SMM command **`0x35A3`**), successive readings showed the fan falling from **2,509 RPM** (Dell CPU **55°C**) to **0 RPM** (**53°C**) and staying stopped for four additional readings around **54°C**. This is strong behavioral evidence that BIOS fan management resumed; the hwmon `MANUAL CONTROL` label alone did not reliably describe that state.
- Later the experimenter described the crucial **AC/S5 connection test** as successful. The available conversation supports **one such user-reported success**, not dozens of cold-start tests or a structured power-cycling validation log.

**Not tested, or not independently confirmed:** full repeat of the nine-minute thermal test on M54FIX; repeated S5 adapter cycles; sleep/resume and all other power-state transitions; long-term reliability; physical readback of the actual programmed EC contents; independent hardware recovery after a bad flash.

## 7. Why would wrong additive checksums break AC/S5?

Separate the **proven facts** from the **mechanism we infer**.

**Directly established:**
- Three independent stock-A14 regions obey 32-bit additive zero-sum invariants.
- The previous experimental images broke those invariants and were associated with an AC/S5 failure.
- M54FIX keeps the same functional fan-control bytes as historical MIN54-QUIET, restoring the region checksums.
- M54FIX booted Linux, exhibited the desired low fan behavior, and was followed by a positive user-reported AC/S5 test.

**Plausible mechanism:** the EC validates the integrity of a firmware region on at least one initialization path; a nonzero sum causes a fallback or error path instead of normal power-management execution. Prior static ARC600 analysis suggested a candidate validator in BOOT-1 around `0x2794`, with helper code near `0x2888`, and a possible alternate path involving the BRIDGE code. A complete, independently reviewed decompilation tracing the exact AC/S5 entry conditions and later effects is **still outstanding**. Do not report this inferred runtime path as an instrumented hardware trace.

**Unresolved questions:**
- Does the validator execute specifically during an AC insertion while the laptop is in S5?
- Is BOOT-2 checksum correction alone sufficient, or do both BOOT-1 and BOOT-2 need to be valid?
- Where exactly does the EC command full fan duty, and why does the POWER handler become unresponsive?
- Which portions, if any, are verified by on-chip BootROM rather than the visible EC flash?
- Could flash state or update sequencing have independently influenced the result?

The external [`eigenmatt/mec-tools`](https://github.com/eigenmatt/mec-tools) project for **different** MEC-equipped machines implements analogous additive *boot-time checksums*. This supports the format interpretation but does not prove the same power-on path in the E5420.

## 8. Lessons worth preserving

1. **Container CRCs are not the same as EC boot-time integrity checks.** The earlier updater wrappers had corrected CRCs while the underlying EC images no longer satisfied their own additive invariants.
2. **A Linux boot does not test the full EC power-state machine.** Plugging in AC while powered off exercised a path not covered by the original fan/thermal tests.
3. **Compare disjoint patches, not just the latest failure.** MIN54 and 66-QUIET had different functional edits yet the same class of AC/S5 incident.
4. **Reconstruct an *exact* known historical intermediate artifact before applying a fix.** Matching the historical SHA-256 made this controlled comparison meaningful.
5. **Treat hashes, static disassembly, dynamic hardware observations, and long-term reliability as different kinds of evidence.** A positive repair attempt strengthens a hypothesis without proving every internal step.

## 9. Safety, provenance, and further work

This is **not a general Dell BIOS/EC flashing tutorial**. Firmware modification carries a real risk of permanent damage, and an independently verified EC recovery method is absent. The repo deliberately omits Dell-owned EC binaries, updater EXEs, PFS payloads, and other proprietary firmware material.

The most useful next steps are **offline**: fully trace the candidate validator, establish the error branch and recovery/BRIDGE semantics, map any available public MEC register descriptions, and compare assembly with the prior disassembly log. Do not rely on the existence of an experimental service interpreter as evidence that EC recovery is safe.

### Related records

- [ARC600 side findings in English](EC_ARC600_SIDE_FINDINGS.md): boot/runtime, timer IRQ, TACH diagnostics, flash-record writer, PS/2 keyboard handling.
- Detailed three-region checksum investigation, original Polish.
- Original AC/S5 postmortem, Polish.
- Full disassembly notebook (87 sections, Polish).
- Historical quiet-fan thermal results, Polish.
- [Exact offline builder source code](../tools/build_min54quiet_from_available.py).

**Evidence-based conclusion:** the data provide a strong controlled indication that not updating the EC image's internal checksum compensation words was responsible for the earlier AC/S5 failure. They do **not yet** reveal the exact ARC600 instruction sequence connecting validation failure to the fan being driven at maximum and the power button becoming unresponsive.
