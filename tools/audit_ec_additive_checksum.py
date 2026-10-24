#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 peter3332
"""Read-only, reproducible EC additive checksum audit for Dell Latitude E5420 A14.

Never writes firmware, USB, EC registers or any binary file. The variants are
reconstructed in memory from an independently verified stock EC image.
The values needed to make an arithmetic sum zero are NOT validated firmware.
"""
from pathlib import Path
from hashlib import sha256
import argparse
import struct

STOCK_HASH = "dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96"
SHA_BY_VARIANT = {
    "A14 STOCK": STOCK_HASH,
    "MIN54": "031f6b4b48af6b4baa9c76dbe9f77d1b007865ff944bef0dc35b488be153d177",
    "MIN54-QUIET": "b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab",
    "66-QUIET": "02322707af66ca66876a69a7d602b3d244a0c696fca7e8b2b386f13fe81e4b2f",
}
MIN54 = {0x2750: (0x66, 0x54), 0x164D6: (0x66, 0x54)}
QUIET = {
    0x216D2: (0xE4, 0xC4),
    0x216D3: (0x0C, 0x09),
    0x216D5: (0x4E, 0x50),
    0x216D6: (0xD8, 0xE4),
    0x216D7: (0x0E, 0x0C),
}
FIRST = 0x1000
LAST_WORD = 0x37FFC
IMAGE_END = 0x38000
MASK32 = 0xFFFFFFFF


def validate_sha(data, expected, variant):
    found = sha256(data).hexdigest()
    if found != expected:
        raise ValueError(f"{variant}: wrong SHA-256; expected {expected}, got {found}")


def create_variant(stock, changes):
    obj = bytearray(stock)
    for offset, (before, after) in changes.items():
        if obj[offset] != before:
            raise ValueError(f"Unexpected stock EC byte at 0x{offset:05X}")
        obj[offset] = after
    assert sum(a != b for a, b in zip(stock, obj)) == len(changes)
    return bytes(obj)


def dword_sum(data, begin, end):
    if begin % 4 or end % 4 or begin > end:
        raise ValueError("Unaligned word range")
    return sum(val[0] for val in struct.iter_unpack("<I", data[begin:end])) & MASK32


def audit(variant, data):
    validate_sha(data, SHA_BY_VARIANT[variant], variant)
    last = struct.unpack_from("<I", data, LAST_WORD)[0]
    before = dword_sum(data, FIRST, LAST_WORD)
    whole = dword_sum(data, FIRST, IMAGE_END)
    computed_last = (-before) & MASK32
    return last, before, computed_last, whole


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--stock",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "work/stock-EC-A14.bin",
        help="verified original EC A14 raw image, default work/stock-EC-A14.bin",
    )
    args = cli.parse_args()
    stock = args.stock.read_bytes()
    if len(stock) != IMAGE_END:
        raise ValueError(f"Wrong stock EC size: {len(stock)} (expected {IMAGE_END})")
    validate_sha(stock, STOCK_HASH, "A14 STOCK")
    images = {
        "A14 STOCK": stock,
        "MIN54": create_variant(stock, MIN54),
        "MIN54-QUIET": create_variant(stock, MIN54 | QUIET),
        "66-QUIET": create_variant(stock, QUIET),
    }
    print("OFFLINE / READ-ONLY. No firmware images generated.")
    print("DW sum: little-endian 32-bit words EC[0x1000:0x38000], modulo 2^32\n")
    print(f"{'variant':14} {'stored final DW':>17} {'sum w/o DW':>14} {'needed DW':>14} {'sum remainder':>16}")
    for name, data in images.items():
        final, before, needed, residue = audit(name, data)
        print(f"{name:14} 0x{final:08X}      0x{before:08X}     0x{needed:08X}      0x{residue:08X}")
    assert audit("A14 STOCK", images["A14 STOCK"])[-1] == 0
    assert all(audit(name, data)[-1] != 0 for name, data in images.items() if name != "A14 STOCK")
    assert all(struct.unpack_from("<I", d, LAST_WORD)[0] == 0xC86347B3 for d in images.values())

    sections = (
        ("BOOT-1", 0x1000, 0x4400),
        ("BRIDGE", 0x4400, 0x5000),
        ("BOOT-2", 0x5000, 0x38000),
    )
    print("\n=== THREE INDEPENDENT ZERO-SUM REGIONS (all inclusive of last DWORD) ===")
    for label, start, end in sections:
        offset = end - 4
        factory = struct.unpack_from("<I", stock, offset)[0]
        before = dword_sum(stock, start, offset)
        assert ((before + factory) & MASK32) == 0
        print(f"\n{label}: EC[0x{start:05X}:0x{end:05X}], compensation DWORD EC+0x{offset:05X} = 0x{factory:08X}")
        print(f"{'variant':14} {'region sum':>12} {'stored DWORD':>13} {'needed DWORD':>13}")
        for name, data in images.items():
            stored = struct.unpack_from("<I", data, offset)[0]
            required = (-dword_sum(data, start, offset)) & MASK32
            residue = dword_sum(data, start, end)
            print(f"{name:14} 0x{residue:08X}    0x{stored:08X}    0x{required:08X}")
        assert dword_sum(stock, start, end) == 0
    assert dword_sum(images["MIN54"], 0x1000, 0x4400) != 0
    assert dword_sum(images["MIN54-QUIET"], 0x1000, 0x4400) != 0
    assert dword_sum(images["66-QUIET"], 0x1000, 0x4400) == 0
    assert all(dword_sum(image, 0x4400, 0x5000) == 0 for image in images.values())
    assert all(dword_sum(image, 0x5000, 0x38000) != 0 for name, image in images.items() if name != "A14 STOCK")
    print("\nResult: the earlier total zero sum is a COMPOSITE of three separately zero-summed regions.")
    print("All three modified images fail BOOT-2; MIN54 and MIN54-QUIET also fail BOOT-1.")
    print("These are mathematical facts, not proof of a runtime or S5 validation mechanism.")
    print("\nResult: stock total is zero-sum; each modified variant violates it.")
    print("This suggests an EC image checksum, NOT proof of an S5 validation routine.")
    print("The calculated 'needed DWORD' values are mathematics only, NOT a flash patch.")


if __name__ == "__main__":
    main()
