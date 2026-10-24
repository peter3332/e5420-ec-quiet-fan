# Reproducing the historical extraction and static analysis (read-only)

This walkthrough assumes you already have a **locally extracted original Dell A14 System BIOS** obtained with BIOSUtilities. The repository does **not** distribute reference Dell binaries.

```bash
cd ~/e5420-ec
BIOS=$(find work/biosutils/Firmware -name '*System BIOS*data.bin' -print -quit)
[ -n "$BIOS" ] && file "$BIOS"
xxd -l 128 "$BIOS"
grep -aob '_FVH' "$BIOS" | head -20
uefiextract "$BIOS" report
```

In one historical environment, `uefiextract` returned error **35** when using a relative output directory with `-o`. A **fresh absolute** output directory worked:

```bash
OUT="$PWD/work/uefi/DellFlashUpdateDxe-absolute"
uefiextract "$BIOS" 6426C814-601A-4116-9E9F-BF9D6F8F254F -o "$OUT" -m body -t 10
file "$OUT/body.bin"
objdump -h "$OUT/body.bin"
```

Expected format: `PE32+ executable for EFI (boot service driver), x86-64`.

Find quick references to known constants in the extracted driver:

```bash
objdump -d -Mintel "$OUT/body.bin" |
  grep -iE -B 6 -A 10 '180011458|180011120|180010808' | head -120
```

Revisit the principal static disassembly ranges:

```bash
objdump -d -Mintel --start-address=0x1800007b0 --stop-address=0x180000910 "$OUT/body.bin"
objdump -d -Mintel --start-address=0x180005cb0 --stop-address=0x180006030 "$OUT/body.bin"
objdump -d -Mintel --start-address=0x180009724 --stop-address=0x1800097a4 "$OUT/body.bin"
objdump -d -Mintel --start-address=0x18000301c --stop-address=0x18000315c "$OUT/body.bin"
objdump -d -Mintel --start-address=0x180002d58 --stop-address=0x180002ed8 "$OUT/body.bin"
```

Verify the exact GUID bytes in the PE file (UEFI GUIDs have a mixed-endian binary representation):

```bash
python3 - "$OUT/body.bin" <<'PY2'
import sys, uuid
p = sys.argv[1]
d = open(p, 'rb').read()
for g in ('3E3DF348-70A6-4A5A-8B8F-A2D2F66DD02C',
          '50DB5F71-D62F-4CDD-9F4F-6ED51395D69D'):
    b = uuid.UUID(g).bytes_le
    print(g, [hex(i) for i in range(len(d)) if d.startswith(b, i)])
print('PFS.HDR.',hex(d.find(b'PFS.HDR.')))
PY2
```

**Do not execute discovered I/O commands automatically or attempt to replicate programming operations on live EC hardware.**

## Full UEFI extraction and the historical stopping point (stage 2)

`UEFIExtract` supports the `all` mode **without `-o`**. Its output goes into `${BIOS}.dump` (the test produced **6,296** files). The message `parseNvarStore: file can't be parsed as NVAR variable store` did not stop extraction in that environment.

```bash
cd ~/e5420-ec
BIOS=$(find work/biosutils/Firmware -name '*System BIOS*data.bin' -print -quit)
uefiextract "$BIOS" all
DUMP="${BIOS}.dump"
find "$DUMP" -type f | wc -l

PE2=$(find "$DUMP" -type f \
  -path '*/175 SmmEventDxe/1 Compressed section/0 PE32 image section/body.bin' \
  -print -quit)
objdump -d -Mintel \
  --start-address=0x180000438 --stop-address=0x180000600 "$PE2"
```

`UEFIExtract` may duplicate GUID bytes in container structures, compression sections, and PE files. When following actual code references, prefer the correct **`0 PE32 image section/body.bin`**, rather than a parent-level `body.bin`. See the historical UEFI EC transport notes.
