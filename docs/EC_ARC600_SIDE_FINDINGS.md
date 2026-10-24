# Dell E5420 EC ARC600 — side discoveries, dead ends, and function map

> **Public research edition.** This is a self-contained English technical analysis distilled from a larger private research archive. Detailed original-language notebooks and raw terminal dumps are intentionally not included to protect local identifiers and private Git history. Technical claims distinguish observed machine-code behavior from inference and open questions.

**Research period:** October 20–24, 2026. Static analysis of the **original, factory Dell A14 EC image**.  
**Main outcome:** [M54FIX checksum-repair case study](M54FIX_AC_S5_CASE_STUDY.md).  
**Primary evidence:** the complete 87-section ARC600 reverse-engineering notebook, retained in Polish with source assembly excerpts.

> **Why preserve the detours?** For several days we investigated initialization, timers, fan hardware access, tachometer diagnostics, flash operations, command queues, and PS/2 keyboard paths in the hope of explaining an EC freeze triggered by connecting AC in S5. The repair turned out to be most strongly associated with recalculating missing EC checksum compensation words. The side investigations remain a useful map of the controller's machine code, device registers, and runtime design — **provided that established instructions are not confused with untested interpretations**.

## Scope and evidence labels

- **[O] Observed:** supported by actual instructions, byte dumps, call relationships, memory accesses, or register arithmetic in stock EC A14.
- **[I] Inferred:** likely interpretation of the observed code but not verified against the vendor's hardware documentation.
- **[H] Hypothesis:** not yet established by complete path analysis or experimental observation.
- **[N] Negative finding:** an investigated simple interpretation was excluded; this does not prove absence of all related failure modes.

Addresses are **offsets into the extracted EC image / virtual code addresses in an ELF that wraps the image at base zero**. They are not necessarily physical processor addresses during every execution context.

## A. Index of investigated subsystems

| Subsystem | Important code / addresses | Original notebook |
|---|---|---|
| EC bootstrap and multiple startup contexts | `0x0000`, `0x03AC`, `0x1000`, `0x2354`, `0x5000`, `0x18FF8` | §2, §33 |
| Timers, IRQ handling, scheduling | `0x2918`, `0x1684C`, `0xA854`, `0x18348`, `0xF81C` | §3, §22, §26, §32 |
| Indexed fan control hardware | `0x2700`, `0x16484`, `0x1DC4`, `0x11488` | §7 |
| Fan-register failure handling | `0x1360`, `0x5650`, `0x5200`, `0x5230` | §8, §9 |
| TACH monitor and fault events | `0x163D4`, `0x80DC`, `0x1D160`, `0xAAF0` | §10, §18 |
| 16-byte records and internal flash writes | `0x18E78`, `0x823C`, `0x1CA3C`, `0x20E3C` | §13, §15, §16 |
| Service monitor and flash opcodes | `0x46B8`, `0x204C0`, `0x20510` | §4 |
| Three-byte command queues and special state | `0x1CAAC`, `0xAAB0`, `0x165C0`, `0x16738` | §42, §47, §50 |
| Keyboard/PS2 and three MMIO channels | `0xBB58`, `0x1A7DC`, `0x8F60`, `0x180DC` | §56, §62, §68 |
| Functions explicitly ruled out as checksum validators | `0x00C0`, `0x063C` | §87 |

## B. Startup code and two execution contexts

See §2, §31–§33, §35, §87.

**[O] The first traced bootstrap path:**

```text
0x0000  initial register clearing
0x0064  SP = 0x8003F0, GP = 0x800100
0x0080  jump to 0x03AC
0x04F2  indirect jump to 0x1000
0x1000  second startup prologue / updated SP and GP
0x1080  jump to 0x2354
0x2354  RAM / runtime preparation
0x2388  call 0x2908 → 0x2918 (timer initialization)
```

**[O]** A second execution context has a vector structure beginning at `0x5000`, a startup at `0x5140`, and a previously traced initialization function `0x18FF8`. These are distinct but cannot be automatically labelled "S0" and "S5" without state evidence.

**[O]** The common `0xF81C` runtime initialization is called directly from `0x190AA` and `0x1A42E`; it prepares the stack, clears RAM `0x800100..0x801FFF`, and initializes a timer-like block. **[H]** Exact startup conditions and mapping to ACPI S-states remain unknown.

**[N]** Previously suspected `0x00C0` manipulates ARC `status32`, while `0x063C` is a parameterized byte-fill routine (in the observed bootstrap path clearing 8 KiB starting at `0x800000`). **Neither is a checksum validator.** See §87 and checksum investigation, section 10.

## C. Fan hardware interface and bounded error recovery

See §7–§10.

**[O] Two initialization implementations** configure the same indexed fan-related MMIO block, `0xF01480`.

```text
0x2700..0x2758     indices/values:
                    0x85=0x19, 0x86=0x10, 0x88=0xF5,
                    0x82=0xAB, 0x83=0x34, 0x87=0x66
                    Minimum Drive operand at 0x2750
                    wrapper 0x1474 → low-level routine 0x1DC4

0x16484..0x164EE  analogous settings
                    Minimum Drive operand at 0x164D6
                    wrapper 0x5784 → low-level routine 0x11488
```

**[O]** Hardware writes put the index in `[base+4]` and value in `[base+8]`. **[I]** The `0x87` field is the fan's Minimum Drive setting, consistent with the measured behavior of the `0x66→0x54` patch. Its vendor-official register meaning has not been independently confirmed.

**[O] The busy-poll loops are finite:**
- `0x1DC4` and `0x11488` each use at most **1,024** BUSY checks for a fan register write.
- `0x1360` and `0x5650` toggle the relevant status bits and use a second bounded wait of up to **10,240** checks, then return `-1`.
- `0x5200` and `0x5230` manipulate the **0x6** interrupt-enable mask in ARC `status32`, implementing conditional critical-section behavior.

**[N]** The simple claim that lowering Minimum Drive to `0x54` directly hangs the EC in an **unbounded BUSY loop writing index 0x87** is contradicted by the code examined: those loops are bounded. This alone does not exclude hardware side effects or some other later failure.

## D. Tachometer fault detection, event records, and internal flash writes

See §10–§20.

**[O] Core call relationships:**

```text
0xAAF0 (periodic-task dispatcher)
   |
   +-- only if [GP−0x7A] == 3 → 0x163D4 (TACH fault monitor)
                                |
                                +-- 0x16568 (measured TACH period)
                                +-- compares period with 0xFF00
                                +-- 0x1C0E8 / 0x1C0C0 (counter threshold 0x1E)
                                +-- 0x80DC → 0x1D160 → 0x1F964 (event flags)
```

**[O]** The dispatcher and TACH monitor both check that `[GP−0x7A] == 3`. There is no proof this internal value represents ACPI S5. The threshold `0x1E` is **30 counts of an uncalibrated unit**, not established as 30 seconds.

**[O]** A record producer near `0x18E78` creates **16-byte entries**. Function `0x823C` reaches `0x1CA3C`, which copies a **248-byte code block** from `0x20E3C..0x20F33` to RAM `0x801E00..0x801EF7`; a call subsequently executes code at `0x61E00` with interrupts masked/modified. The copied code accesses `0xFF3900` (data), `0xFF3904` (address), and `0xFF3908/0xFF390C/0xFF3910` (operation/status/control); it reads entries at `0x61F00+4*i`.

**[I]** This strongly resembles programming a persistent diagnostic record via a RAM-resident helper, likely because flash programming cannot safely execute from the same flash bank. An alias or execution window linking `0x801E00` and `0x61E00` is plausible but needs MEC documentation.

**[N]** No direct command to set **100% fan PWM** or disable POWER was found in the investigated TACH/event path. That path was **not shown** to execute during the earlier AC/S5 incident.

## E. Timers, interrupt handlers, periodic flags

See §3, §21–§33, §48.

**[O]**
- `0x2918` and `0x1684C` contain analogous initialization of the `0xF00C00` block and an *unbounded local* wait for a hardware status bit to clear.
- `0xA854` implements counters and periodic flags. The observed thresholds are **10, 125, and 1,000 calls** to this function. At the appropriate 1,000-call transition it sets `[GP−0x98]=1`.
- A traced interrupt-context chain is `0x18348 → 0x183A4 → 0x18418 → 0xA854` when the relevant hardware pending bit is set.
- `0xEE6A` and `0xFD04` clear `[GP−0x98]` and invoke `0xAAF0`; one variant also calls `0x11D08`.
- `0x19F80` has a separate polling wait for `[GP−0x98]` with **no local software timeout**.
- `0xF00C80` is a timer-like block configured with `0x3E8=1000` in `0xF00C88` and `0xF00C8C`.

**[I/H]** It likely implements a task clock or a timebase for events, but **1,000 invocations do not automatically mean 1,000 milliseconds**. The actual IRQ frequency and behavior while in S5 are not established.

## F. Service monitor and flash opcodes

See §4, §15–§16.

**[O]** Code writes `0x5000` or `0x60000` to ARC `int_vector_base` in different contexts. Two similar command interpreters around `0x46B8` and `0x204C0` receive opcodes through MMIO `0xFF01F0`.

| Opcode | Code | Observed implementation | Confidence |
|---|---|---|---|
| `0xEC` | `0x2054C` | Memory-controller operation `0x103` | [I] likely erase |
| `0xED` | `0x20590` | Read a DWORD with bounds related to `0x38000` | [O] read |
| `0xEE` | `0x205D4` | Supply address/data to memory controller, operation `0x102` | [I] likely program |
| `0xF2` | `0x20638` | Register sequence followed by polling | [H] exit/reset |

This is useful evidence of a service interface, **not an independently validated EC rescue mechanism**. No live experiment with these opcodes is advised.

## G. Three-byte queues and the unexplained sequence 02 06 04 03 05

See §35–§55.

**[O]** At least **15 direct call sites** of `0x1A3B4` were found; they pass different cause codes. A path to `0x1A320` can process previously recorded codes, conditionally record an event, and enter some form of initialization. Without additional information it is not correct to label this an "AC power handler".

**[O]** A dispatcher at `0x1CAAC` processes **three-byte records** indexed within RAM around `0x80002A`. Opcode `0x19` modifies `[GP−0x5B]`. Calls involve `0xAAB0`, a queue flag at `[GP−0x99]`, a halfword counter `MEM16[0x80002A]`, and `0x165C0`. The latter's operation is gated by `[GP−0x5E]==0xFF` and only its special empty-index case also depends on internal state 3.

**[O]** A five-element state machine at `0x16738` compares input values with data stored at `0x216A4`:

```text
02 06 04 03 05
```

When additional argument and `[GP−0x58]` conditions are met, completing this sequence enables special state `[GP−0x5E]=0xFF`.

**[I]** These are the PC Scan Code Set 1 codes for keys `1–5–3–2–4`, and other analyzed paths genuinely perform Set 2 → Set 1 translation. **[H]** The human-interface significance of the sequence — service code, recovery shortcut, or other event pattern — remains unproven. It should **not** be presented as a safe key combination to try.

## H. Keyboard code, three MMIO channels, and a complete IRQ path

See §56–§77.

This is among the most completely traced **side branches**.

**[O] Data path:**

```text
0x180DC: interrupt handler
   reads IRQ status at 0xF0C0BC (notably bits 13,14,15)
   sets pending flags in 0x8002A8 / 0x8002A9 / 0x8002AA
   writes handled IRQ mask to 0xF0C0B4 (candidate ACK)
      |
      v
0xF022..0xF05A: consumes each channel's pending flag
      |
      v
0x8F60(channel): tests software status GP−0x18/−0x17/−0x16
      |
      v
0x5D7C(channel) → 0x1A7DC:
   0 → MMIO 0xF08800
   1 → MMIO 0xF08880
   2 → MMIO 0xF08900
      |
      v
0xBB58 → 0xBB7E/0xBB9A/0xBC00:
   PS/2 F0/E0 prefixes and make/break handling
   Set 2 → Set 1 lookup table at 0x2144C
```

**[O]** The translation table was verified against actual stock-A14 bytes, e.g. `0x16 → 0x02` (key 1). The image also contains a reverse translation path and ways to submit synthetic events. The three channels need not correspond to three physical PS/2 ports; their physical wiring is unknown.

**[O]** Function `0x180DC` has a full interrupt-entry prologue and a symmetric epilogue ending in `j.f [ilink]`. `0xF0C0B8` is manipulated as an IRQ enable/mask register: `0x7C34` clears bits 13–15, and `0x80AC` conditionally enables selected bits. The `0xF0C0B4` write is a strong candidate for acknowledging interrupts, but the exact W1C behavior is unverified.

**[N]** `0x7584` and `0x75D0` only update software channel status bytes in RAM in the examined code, rather than directly programming MMIO. No causal connection between the keyboard branch and AC/S5 was demonstrated.

## I. Why these dead ends matter

| Early theory | Result |
|---|---|
| Changing Minimum Drive to 0x54 blocks a fan-register write forever | **Not in the observed helpers:** polling loops are bounded (§7–§9). Other indirect effects cannot be ruled out. |
| A counter value of 1000 means 1000 ms | **Not demonstrated:** interrupt tick frequency is unknown (§22, §29). |
| `[GP−0x7A]==3` means ACPI S5 | **Unknown:** the EC's internal state machine has not been mapped to ACPI (§18–§19). |
| TACH fault or flash-event logging directly drives 100% PWM | **No such path found** in the examined code (§10, §16). |
| `0x00C0` and `0x063C` verify firmware checksums | **False:** ARC status manipulation and `memset` respectively (§87). |
| Keyboard scan-code sequence explains the AC/S5 failure | Parser identified, causal relationship absent (§50, §77). |
| Service erase/program opcodes prove a safe recovery method | **False:** no tested independent EC recovery method (§4). |

The repair-relevant additive checksum discovery is described separately in the [M54FIX report](M54FIX_AC_S5_CASE_STUDY.md) and in the primary checksum research notebook. We preserve **incorrect hypotheses and subsequent corrections**, instead of editing the history to make the final explanation look obvious.

## J. ARC600 disassembly pitfalls and reproducibility

The research yielded several practical cautions:

- The `.as` addressing suffix scales instruction offsets in **words (×4)**: `0xF0BF64 + (0x56 << 2) = 0xF0C0BC`.
- `0xFFFFFF86` interpreted as signed32 is **−0x7A**, not −0x86; `0xFFFFFFA2` is **−0x5E**, not −0xA2.
- `GP+0x7A` and `GP−0x7A` are entirely different variables (e.g., a TACH-related halfword and the internal state byte).
- Disassemblers may display a call as `bl 0x2354 ;0x13084`: the **commented target after the semicolon** is the true absolute destination in that context. Text grep can create incorrect call graphs.
- A disassembly window may start **in the middle of a multi-byte instruction** or interpret ASCII/table data as code. Validate prologues and direct callers.

Recreate the most informative dumps **offline**, using the ELF wrapper around your own original stock-A14 EC:

```bash
cd ~/e5420-ec
arc-linux-gnu-objdump -d -M cpu=arc600,hex \
  --start-address=0x180d0 --stop-address=0x18290 \
  work/stock-EC-A14.elf

arc-linux-gnu-objdump -d -M cpu=arc600,hex \
  --start-address=0x20e3c --stop-address=0x20f34 \
  work/stock-EC-A14.elf

arc-linux-gnu-objdump -s -j .text \
  --start-address=0x2144c --stop-address=0x21480 \
  work/stock-EC-A14.elf
```

These commands only read local files. They neither write to the live EC nor access its MMIO.

## K. Other related investigations

This catalogue covers primarily October 20–24. Earlier separate records include:

- Dell SmmEcIoDriver interface, host EC ports 0x910/0x911.
- Discovery of the Minimum Drive operand.
- Dell PFS and PE packaging, CRC and signatures.
- The original AC/S5 incident and abandoned hypotheses.
- [Read-only additive checksum auditor](../tools/audit_ec_additive_checksum.py).

**Final scope statement:** the identified TACH, keyboard, timer, IRQ, flash logging, and command-queue mechanisms are genuine components of the image as reconstructed from code, but **none was shown to be the cause of the original S5 lockup**. Keep the entire original notebook, with its corrections, as primary evidence.
