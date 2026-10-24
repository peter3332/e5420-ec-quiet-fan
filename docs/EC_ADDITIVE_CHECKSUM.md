# Dell Latitude E5420 A14 — discovery of internal additive EC checksums

> **Public research edition.** This is a self-contained English technical analysis distilled from a larger private research archive. Detailed original-language notebooks and raw terminal dumps are intentionally not included to protect local identifiers and private Git history. Technical claims distinguish observed machine-code behavior from inference and open questions.

**Original investigation:** October 24, 2026.  
**Status note:** This translates and consolidates the investigation as it stood when the three separate checksum regions were discovered, with a subsequent experimental update. Its original Polish research notebook preserves historical calculations, intermediate assumptions, hexdumps, and their corrections. For the later hardware result, see [M54FIX](M54FIX_AC_S5_CASE_STUDY.md).

> **Important correction to the earliest calculations.** The zero sum over `EC[0x1000:0x38000]` is the sum of **three separately zero-balanced regions**: `[0x1000,0x4400)`, `[0x4400,0x5000)`, and `[0x5000,0x38000)`. Their compensation DWORDs are at `0x43FC`, `0x4FFC`, and `0x37FFC`. The original MIN54, MIN54-QUIET, and 66-QUIET all broke region 3; MIN54 and MIN54-QUIET also broke region 1. An offline repair of regions 1 and 3, M54FIX, later produced a positive user-reported AC/S5 test. This strengthens the integrity-check hypothesis but does not establish the exact execution path or isolate which checksum was necessary.

## 1. Reproducing the AC/S5 failure with disjoint firmware patches

The Dell A14 PFS contains a **`0x38000` = 229,376-byte EC image**; its decompressed payload begins at PFS offset `0x400510`. Earlier comparison found no changes to the 4 MiB System BIOS contents in the modified update packages, and precisely identified the changes made to the EC data.

| Variant | Bytes at `0x02750` / `0x164D6` | Profile A bytes at `0x216D0` | User-observed AC insertion in S5 |
|---|---|---|---|
| Factory A14 | `66 / 66` | `32 48 E4 0C 41 4E D8 0E` | Normal after restoration |
| MIN54 | `54 / 54` | Factory | **Failure** |
| MIN54-QUIET | `54 / 54` | `32 48 C4 09 41 50 E4 0C` | **Failure** |
| 66-QUIET | `66 / 66` | `32 48 C4 09 41 50 E4 0C` | **Failure** |

The two functional offsets changed in MIN54 do **not overlap** the five offsets changed in 66-QUIET. Thus the replacement `0x66→0x54` is not a necessary condition for the reported failure, assuming each test used the intended, correctly identified image. Common factors include changing the underlying EC payload, rebuilding the updater, and the resulting state of the EC after flashing.

Recorded EC image SHA-256 values:

```text
stock A14      dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96
MIN54          031f6b4b48af6b4baa9c76dbe9f77d1b007865ff944bef0dc35b488be153d177
MIN54-QUIET    b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab
66-QUIET       02322707af66ca66876a69a7d602b3d244a0c696fca7e8b2b386f13fe81e4b2f
```

## 2. Initial discovery: a zero sum of 32-bit words

The final 16 bytes of the stock extracted EC contain twelve `0xFF` bytes followed by:

```text
0x37FF0: FF FF FF FF FF FF FF FF FF FF FF FF B3 47 63 C8
                                                    ^^^^^^^^^^^
                                             DWORD LE = C86347B3
```

Initially the entire interval `[0x1000,0x38000)` was considered as one large region. Its words obey:

```text
W[i] = uint32_le(EC[0x1000+4*i:0x1004+4*i])

sum(W) modulo 2^32 = 0                 (stock A14)
sum(all W except final word) = 0x379CB84D
final DWORD at 0x37FFC    = 0xC86347B3
0x379CB84D + 0xC86347B3 ≡ 0 (mod 2^32)
```

This exact arithmetic match suggested a **compensating additive checksum word**, independent from CRC32. It also fit an earlier updater analysis: the `DellFlashUpdateDxe` routine at `0x18000301C` skipped the first two `0x800`-byte blocks `0x0000..0x0FFF`.

**Historical limitation:** the original assumption that the entire interval was a single checksum-protected region was refined later (section 8). The combined sum remains mathematically correct, but the compensation word at `0x37FFC` belongs to region 3, not necessarily to the entire interval.

## 3. Historical whole-interval checksum table — not a patch recipe

The earliest auditor computed:

```text
remainder = sum(unpack_uint32_le(EC[0x1000:0x38000])) & 0xffffffff
```

| Image | Whole-interval sum | Stored word at 0x37FFC | Sum before 0x37FFC | DWORD required to make the *whole interval* zero |
|---|---|---|---|---|
| A14 stock | `0x00000000` | `0xC86347B3` | `0x379CB84D` | `0xC86347B3` |
| MIN54 | `0xFFEDFFEE` | `0xC86347B3` | `0x378AB83B` | `0xC87547C5` |
| MIN54-QUIET | `0xFADA01EE` | `0xC86347B3` | `0x3276BA3B` | `0xCD8945C5` |
| 66-QUIET | `0xFAEC0200` | `0xC86347B3` | `0x3288BA4D` | `0xCD7745B3` |

In every modified image the last stored DWORD remained equal to stock. These numbers diagnose a violated invariant; they were **not** experimentally verified as correction words in the controller.

A negative control was also calculated: ordinary EC CRC32 including the last DWORD was `0x3EA5748A`, and CRC32 without the last four bytes was `0x66D3CC88`. Neither those values nor their complements match `0xC86347B3`. The matched structure is a straightforward additive sum, not standard CRC32.

## 4. What the first offline audit did and did not establish

**Observed from files:** the stock EC had a zero sum, the three patched images did not, and the compensating final DWORD remained at its factory value. Independently updated EC/PFS CRC32 fields in the outer firmware packaging could be correct while this internal invariant failed.

The Dell PFS also contains a separate 256-byte `Embedded Controller.data.sig` and the updater PE has Authenticode-related content. Neither proves that its signature bytes are written to EC flash. Reusing an old Authenticode block with modified executable content does **not** produce a valid signed updater.

**Initially unproven:** the implementation of the validator, when it runs during EC reset or AC/S5, whether BootROM or EC flash code enforces the checksum, how a nonzero sum affects fan/POWER, whether the updater automatically rewrites the final word, and the exact physical flashed bytes. There is no verified independent EC rescue path.

## 5. Reproducing arithmetic safely offline

Use the project's [`tools/audit_ec_additive_checksum.py`](../tools/audit_ec_additive_checksum.py) with the original extracted `work/stock-EC-A14.bin` and the historical inputs specified by the script. It computes each of the three independent region sums and displays stored and required compensation words **without writing firmware or issuing EC commands**.

Relevant source records:

- Original AC/S5 failure postmortem
- Dell PFS and PE signature investigation
- ARC600 disassembly notebook

## 6. A related MEC checksum implementation — important but not device-specific

The independent public project [eigenmatt/mec-tools](https://github.com/eigenmatt/mec-tools), developed for **other (Lenovo) MEC-based devices**, includes `mec_csum_boot.c`, which uses the same style of 32-bit additive checksum:

```c
unsigned int csum = 0;
for (p = base+start; p < base+end; p += 4)
    csum += *(unsigned int *)p;
csum = -csum;
```

It stores a 32-bit compensation DWORD at a designated location and explicitly calls these **boot-time checksums**. This is independent evidence that the algorithm is used in the broader MEC firmware ecosystem. Its offsets, encryption/decryption, repacking scheme, and safety properties **cannot** be transplanted to an E5420 MEC5055.

## 7. On-device offline audit and 0x800-byte update blocks

The checksum auditor was independently run on the physical Latitude under Xubuntu **as an offline file-analysis program**, not a live EC interrogation. The verified factory EC hash was:

```text
dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96
```

The auditor's historical whole-interval result:

```text
variant         stored final DW  sum w/o DW  needed DW   sum remainder
A14 STOCK       0xC86347B3      0x379CB84D  0xC86347B3 0x00000000
MIN54           0xC86347B3      0x378AB83B  0xC87547C5 0xFFEDFFEE
MIN54-QUIET     0xC86347B3      0x3276BA3B  0xCD8945C5 0xFADA01EE
66-QUIET        0xC86347B3      0x3288BA4D  0xCD7745B3 0xFAEC0200
```

The independent stock-versus-66-QUIET comparison showed:
- Exactly five changes at `0x216D2`, `0x216D3`, `0x216D5`, `0x216D6`, `0x216D7`.
- Only one modified `0x800`-byte block: `0x21000..0x217FF`.
- The last `0x800`-byte block, `0x37800..0x37FFF`, was byte-identical to stock, including `0x37FFC = B3 47 63 C8`.

Previous code analysis of the Dell updater, `DellFlashUpdateDxe:0x18000301C`, indicated an algorithm that reads and compares **0x800-byte blocks** and skips those identical to the provided payload. If the physical final block already contained stock bytes, it is reasonable to infer the updater would skip it when flashing 66-QUIET and thus leave its original compensation word in place. That reasoning does **not** substitute for a physical after-flash readback or prove the S5 runtime behavior.

## 8. Discovery of three separate zero-balanced regions

Searching all word-aligned possible start offsets `start` such that the suffix sum to `0x38000` was zero found exactly **three**:

```text
0x1000, 0x4400, 0x5000
```

In addition, each of the resulting three adjacent nonoverlapping intervals ends in its **own** mathematically exact compensation DWORD.

| Working region name | Half-open interval | Compensation offset | Stock DWORD | Stock sum |
|---|---|---|---|---|
| Region 1 / BOOT-1 | `[0x1000,0x4400)` | `0x43FC` | `0x2704FF56` | 0 |
| Region 2 / BRIDGE | `[0x4400,0x5000)` | `0x4FFC` | `0x2093D4E7` | 0 |
| Region 3 / BOOT-2 and later code | `[0x5000,0x38000)` | `0x37FFC` | `0xC86347B3` | 0 |

```text
stored_last_dword
    == (-sum(uint32_le_words(region_excluding_last_dword))) & 0xffffffff
```

Separate residual sums:

| Image | Region 1 | Region 2 | Region 3 |
|---|---|---|---|
| Stock A14 | `00000000` | `00000000` | `00000000` |
| MIN54 | `FFFFFFEE` | `00000000` | `FFEE0000` |
| MIN54-QUIET | `FFFFFFEE` | `00000000` | `FADA0200` |
| 66-QUIET | `00000000` | `00000000` | `FAEC0200` |

Thus **region 3 is the only independently zero-balanced region violated by every previous failing variant**. This is stronger evidence of a common structural problem than the initial overall-sum calculation.

**Essential correction to section 3:** The historical "needed DWORD" values listed there balance the *whole combined interval*, rather than specifically correcting region 3. For example MIN54 region 3 considered in isolation would require `0xC87547B3` arithmetically, **not** `0xC87547C5`. Neither should be described as a successfully tested flash patch.

The checksum auditor was revised to compute all three independent sums and expose `region sum`, `stored DWORD`, and `needed DWORD` for each. The original combined-sum output was retained for historical reproducibility.

The checksum boundaries also coincide with distinct ARC code contexts that had already been recognized at `0x1000` and `0x5000`. This supports separately structured EC firmware segments, **not** a proven BootROM validation procedure.

## 9. Bootstrap at 0x03AC and the independent 0x4400 vector header

A read-only disassembly of the authentic stock A14 ELF revealed:

**`0x03AC..0x04FA`:**
- Save `r13,r14,blink`; call `0x00C0` from `0x03B2`; set up SP `0x800400`, clear FP.
- Call `0x063C` at `0x03D2`.
- Configure hardware registers including `0xF0CC9C`, `0xF0FC3C`, `0xF01400`; execute clearing loops.
- Construct `r0=0x1000` and finally execute `jl_s [r0]`, transferring to the entry at `0x1000`.

No obvious DWORD-accumulation loop for all of region 1 or 3 is visible **in that extracted instruction window**. Called helpers, other flash code, and on-chip BootROM are separate possibilities.

**Independent entry under `0x4400`:**

```asm
4400: j 0x60018
4408: j 0x60008
4410: j 0x60010
4418: mov sp,0x801000
4424: mov fp,0
4428: mov gp,0x800c00
4430: j 0x602b8
```

The targets `0x60008`, `0x60010`, `0x60018` and `0x602B8` lie beyond the archived `0x38000`-byte image. Their physical mapping remains unidentified. Other examined service-monitor code sets ARC `int_vector_base=0x60000` at `0x46C8` and `0x204D0`, providing a related reference to that address space.

**Inference:** region 1 ends in a compensation word at `0x43FC`, region 2 begins at `0x4400` with genuine ARC jump-table entries and ends with its own word at `0x4FFC`, and region 3 begins at `0x5000` with a separate startup/vector context. This structure is strong evidence of a segmented boot-capable image, though it does not identify the enforcing validator nor show any relation to S5 execution.

## 10. Negative result: 0x00C0 and 0x063C are not validators

A subsequent read-only decompilation directly resolved the two bootstrap helper functions.

**`0x00C0` alters processor status rather than calculating a checksum:**

```asm
0x00C0: lr   r0,[status32]
0x00C4: bic  r0,r0,0x6
0x00C8: j.d  [blink]
0x00CC: flag r0
```

That clears interrupt-related status bits and returns. Nearby entry points also manipulate `status32`; they do not accumulate EC image DWORDs.

**`0x063C` is a byte-fill routine, not a sum:**

```asm
0x063C: st.aw fp,[sp,-4]
0x0644: mov_s r3,r0
0x0646: cmp_s r2,0
0x0648: sub_s r2,r2,1
0x064A: beq_s 0x0652
0x064C: stb.ab r1,[r3,1]
0x0650: b_s 0x0646
0x065A: j_s [blink]
```

At its observed caller `0x03C6..0x03D2`, the arguments are `r0=0x800000`, `r1=0`, `r2=0x2000`, meaning an **8 KiB memory clear**.

The raw image hex dump independently confirms:

```text
0x43FC: 56 FF 04 27  (LE 0x2704FF56)
0x4400: genuine ARC jump to 0x60018
0x4FFC: E7 D4 93 20  (LE 0x2093D4E7)
0x5000: genuine ARC vector jump to 0x5140
```

These are concrete positive results for segmentation and **negative results for two specific candidate checksum routines**. Whether MEC5055 BootROM checks the compensators, and under which power events, remains unresolved.

## 11. Update after the M54FIX experimental success

M54FIX corrected the two violated compensators in the historical MIN54-QUIET image while preserving its exact seven functional edits. The resulting EC SHA-256 was:

```text
90648894233eca7b25ee2fc53922254988c7a764e7f582c429ee34f175e59fb8
```

On the physical Latitude the new image flashed, Linux started, the intended low-speed fan behavior and BIOS-auto stopping behavior were observed, and **one AC insertion while in S5 was reported successful**. This is strong evidence that internal checksum integrity matters, but **not** evidence of exact BootROM enforcement, a particular error flag, or the hardware mechanism behind maximum fan speed.

See the [M54FIX case study](M54FIX_AC_S5_CASE_STUDY.md) for the actual changed bytes, updated SHA-256 records, build process, and explicit limits. No further flashing is recommended without independent EC recovery capabilities.
