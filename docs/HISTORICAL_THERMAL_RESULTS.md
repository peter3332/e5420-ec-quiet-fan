# Dell Latitude E5420 A14 — historical fan-curve experiment results (October 13, 2026)

> **Public research edition.** This is a self-contained English technical analysis distilled from a larger private research archive. Detailed original-language notebooks and raw terminal dumps are intentionally not included to protect local identifiers and private Git history. Technical claims distinguish observed machine-code behavior from inference and open questions.

> **Retrospective safety context.** This translates the substance of the original October 13 results, which were subsequently **withdrawn as a final firmware-safety judgment on October 19** following the AC/S5 EC freeze. On October 24 the missing internal additive EC checksums were identified, and a checksum-corrected M54FIX image subsequently had one user-reported successful AC/S5 test. Do not interpret these historical thermal observations as proof that the original uncorrected MIN54-QUIET is safe. See the [English postmortem](AC_S5_POSTMORTEM.md) and [M54FIX report](M54FIX_AC_S5_CASE_STUDY.md).

## 1. What the experimenter originally wanted

The goal was a quieter, automatically regulated Dell E5420: reduce the first BIOS-controlled fan stage from about **3,300 RPM** to **2,500 RPM**, while retaining higher stages and thermally protective behavior. The experimenter considered ~2,500 RPM **virtually inaudible**, and did not mind the brief startup boost.

On October 13, after comparing MIN54-QUIET and MIN54-QUIET2, the experimenter reported returning to the first quiet profile. This was the **historical selection at that time**, superseded after the later power-state failure.

## 2. Historical MIN54-QUIET configuration

| Parameter | Value | Status at October 13 |
|---|---|---|
| Base | Dell Latitude E5420 BIOS A14 | Original reference |
| Minimum Drive, two EC locations | `0x54` at `0x2750` and `0x164D6` | Retained from MIN54 |
| First BIOS AUTO stage | 2,500 RPM target; **2,522–2,528 RPM measured** | Modified |
| First entry thermal bytes | **50 / 72°C**, `32 48` | Same as MIN54-AUTO |
| Second BIOS AUTO stage | 3,300 RPM target; **3,340–3,352 RPM measured** | Modified |
| Second entry thermal bytes | **65 / 80°C**, `41 50` | Second byte 78→80 vs MIN54-AUTO |
| Third BIOS AUTO stage | **4,300 RPM**, measured ~4,290–4,311 RPM | Unchanged |
| Third entry thermal bytes | **74 / 85°C**, `4A 55` | Unchanged |
| Further profile A entries | Stock, including special `0x5356` | Unchanged |
| Other thermal profiles B/C | Same as MIN54 | Unchanged |

The first three profile A entries, at `EC[0x216D0]`, are:

```text
32 48 C4 09 | 41 50 E4 0C | 4A 55 CC 10
```

The nearby header at `0x216CC` is `81 43 00 00`, including `0x43 = 67`; in practical tests the fan started at approximately **67°C** according to Dell CPU temperature. This strongly supports, but does not formally prove, the proposed interpretation of these bytes as thermal thresholds.

## 3. Evolution of the profiles

| Image | First BIOS AUTO stage | Second stage | Main finding |
|---|---:|---:|---|
| Stock A14 / MIN54 (Minimum Drive only) | ~3300 RPM | ~3800 RPM | BIOS AUTO retained stock stages; manual MIN54 SMM could reach ~2267 RPM |
| MIN54-AUTO | ~2267 RPM | ~3800 RPM | Quiet first stage, but sustained one-core load caused a quick transition to ~3800 RPM |
| **MIN54-QUIET** | **~2525 RPM** | **~3350 RPM** | Quiet first stage, lower second stage, third retained; complete short thermal test |
| MIN54-QUIET2 | ~2600 RPM | ~3345 RPM | Moving first transition from 72→74°C did not extend first-stage time; reached 85°C cutoff |

Earlier Minimum Drive testing also included MIN60, MIN58, MIN50, and MIN54 (MIN54 original notes, MIN60 original notes). MIN50 was unstable at lower targets. MIN54 produced five successful starts from a stopped fan when manually controlled through SMM.

## 4. Comparable BIOS AUTO thermal runs

All observations came from **one laptop**, using separate runs of `tools/run-thermal-auto-test.sh --cool 60`.

The nine-minute / **540-second** schedule consisted of 60 s idle; 60 s single-process integer load; 60 s cooling; 60 s single-process floating-point load; 60 s cooling; 60 s all-core CPU load (three processes); 60 s cooling; 60 s approximately 32 MiB RAM load; 60 s final cooling. Sensors were `coretemp` and `dell_smm`. This synthetic profile is **not** equivalent to everyday use; approximate transition times reflect terminal output printed every 5 seconds, while local CSV telemetry was sampled every 0.5 seconds.

| Observation | MIN54 | MIN54-AUTO | **MIN54-QUIET** | MIN54-QUIET2 |
|---|---:|---:|---:|---:|
| Integer load, first→second fan stage | No change (~3300 throughout 60 s) | ~15 s then ~3800 | **~30 s then ~3350** | ~30 s then ~3345 |
| Float load, first→second stage | No change (~3300 throughout 60 s) | ~25 s then ~3800 | **~45 s then ~3340** | ~40 s then ~3340 |
| All-core, transition to ~4300 | ~25 s | ~30 s | **~30 s** | ~25 s |
| Peak `coretemp` in printed all-core readings | ~83°C | ~82°C | **~83°C** | 84°C by 55 s, then **85°C cutoff** at 59.5 s |
| Completed full nine-minute schedule | Yes | Yes | **Yes; no 85°C cutoff** | **No; stopped at cutoff** |
| Time to 0 RPM during post-integer cooling | ~20 s | ~25 s | **~35 s** | ~30 s |
| Time to 0 RPM during post-float cooling | ~15 s | ~35 s | **~30 s** | ~25 s |

**MIN54-QUIET:** with an **85°C** stop limit, the fan increased from around 3315 to approximately **4,300 RPM** during the all-core phase near a CPU reading of **80–81°C**. Subsequent printed core temperatures reached **~83°C**. During cooling the fan returned to ~2,500 RPM and later reached 0 RPM near a Dell CPU indication of **50°C**. The full nine-minute run completed.

**MIN54-QUIET2:** the first-to-second transition appeared around Dell CPU **74°C**, versus **72°C** on QUIET, supporting the inferred meaning of `0x216D1`. Raising both the first-stage speed (2,500→2,600) and threshold (72→74°C) did **not** extend first-stage duration: ~30 s in both integer-load runs; ~45 s (QUIET) vs ~40 s (QUIET2) for the float-load comparison. Late in the all-core phase `coretemp` reached **85°C**, and the test correctly stopped at its cutoff, below the machine's reported `high=86°C`. This single run is **not** evidence of a statistically significant difference or an EC malfunction; initial conditions may differ. It was nonetheless sufficient for the experimenter to reject the higher threshold.

**Different workload caution:** a separate `taskset -c 0 timeout ... yes` load is not the same as Python's integer/float tasks. QUIET did not advance to the second stage during 45 s of the `yes` workload; nor did QUIET2 during 60 s of `yes`. Those observations do **not** imply the two firmware versions behave identically during the controlled Python profile.

## 5. Local CSV data (not included in the repository)

The four recorded paths were:

```text
logs/bios-auto-thermal-20261012-235039.csv    baseline MIN54
logs/bios-auto-thermal-20261013-002005.csv    MIN54-AUTO
logs/bios-auto-thermal-20261013-005411.csv    MIN54-QUIET
logs/bios-auto-thermal-20261013-011950.csv    MIN54-QUIET2
```

These local files contained half-second samples but are excluded by `.gitignore`. This report's comparisons were derived from the pasted terminal outputs, not an independent reading of every CSV sample. Calculating full-run statistics would require the original local CSV files.

## 6. Historical build identities and reproducibility

**Original MIN54-QUIET (October 13):**
- Local EC file `ec-min54-quiet.bin`: SHA-256 **`b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab`**.
- Local unsigned EXE `work/E5420A14-min54-quiet-FINAL-UNSIGNED.exe`, named **`M54Q.EXE`** on the FreeDOS USB: SHA-256 **`b69263839c45631b2d67ac013769e2afc3af86d96f9c93177846ffa4bcb72a99`**.
- Builder: `tools/build-min54-quiet.py`. Offline checks: exactly five changes vs MIN54-AUTO; EC/PFS CRC, zlib compression size 2,660,734 B with 2 B padding, PE checksum, and an independent BIOSUtilities extraction succeeded.

**Historical MIN54-QUIET2:**
- EC SHA-256: `52001a334181fe8fa726d3e9cac83d43321c37f38bf576aba0f27df26dcf1005`.
- EXE SHA-256: `fa61bbf66212e8211b6003e8d8481caa164db8ca58dcdc6fbfa81d39fae40874`.
- Builder: `tools/build-min54-quiet2.py`. Compared with QUIET, changed only `0x216D1:48→4A` and speed `0x216D2..3:C4 09→28 0A`.

These were unsigned modifications of proprietary Dell firmware. The original cryptographic signature is **not valid** for the modified executables. Offline validation and successful flashing on one laptop do not replace physical flash readback, broad system qualification, or a verified independent EC recovery procedure. The test conditions do not cover every ambient temperature, clogged cooling hardware, sustained workload, or sensor fault.

## 7. The historical decision and its later revision

**Decision as recorded October 13:** remain on MIN54-QUIET at **2,500 / 3,300 / 4,300 RPM**; do not raise thresholds further; consider the acoustic project complete. This was based on a quiet first stage, a tolerable spin-up transient, and QUIET2's lack of benefit in the short synthetic test.

**Revised interpretation after October 19:** the uncorrected build caused a serious problem on AC insertion in S5. The October 13 conclusion about a finished safe solution was withdrawn, even though the reported RPM/temperature measurements remained valid for the conditions tested.

**Update after October 24:** M54FIX corrected the additive compensation words without changing the functional fan curve, and had a successful user-reported AC/S5 insertion on the tested E5420. This is a new and much stronger result, but there has been **no full retest of this corrected image across all power states and thermal conditions**. The experiment remains single-device research, not a shipping firmware recommendation.
