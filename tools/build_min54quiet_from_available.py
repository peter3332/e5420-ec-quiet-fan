#!/usr/bin/env python3
"""Offline reconstruction of the *historically tested* MIN54-QUIET + EC additive checksums.

Dell E5420 A14. Pure Python 3 standard library. Nothing is flashed or sent to EC.
Never use an output as evidence of successful hardware validation.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
OUT_EC = WORK / 'EC-MIN54QUIET-CHECKSUMMED.bin'
OUT_EXE = WORK / 'E5420A14-min54quiet-CHECKSUMMED-UNSIGNED.exe'

# Authenticated source hashes from the E5420 project build scripts.
SOURCES = (
    ('stock', ROOT / 'firmware/E5420A14.exe', WORK / 'stock-EC-A14.bin',
     '8fef5ea2dbaac0dd91b9b11663e4cf2eacfc86c50bec7db4a62a5b4d36ef0d1e',
     'dcb39da2e579f233cfdfce3ac5da77b4430d50a8b6c4eb030d1bf9ff2e510a96'),
    ('66-QUIET', WORK / '66QUIET.EXE', WORK / 'EC-66QUIET.bin',
     'f14d4b084d6b7e88a266ddf2ef3b815eeed6f3bc949efb9630d75e0cf087f66a',
     '02322707af66ca66876a69a7d602b3d244a0c696fca7e8b2b386f13fe81e4b2f'),
    ('MIN54-QUIET historical', WORK / 'E5420A14-min54-quiet-FINAL-UNSIGNED.exe', ROOT / 'ec-min54-quiet.bin',
     'b69263839c45631b2d67ac013769e2afc3af86d96f9c93177846ffa4bcb72a99',
     'b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab'),
)

EXPECTED_HISTORICAL_QUIET_SHA = 'b20835e61b5f96db28194ab8a63f383b170578969255728ef21565f7813f35ab'
EC_LEN = 0x38000
PFS_LEN = 5959851
PFS_EC_START = 0x400510
PFS_EC_CRC = PFS_EC_START - 8
PFS_CRC = PFS_LEN - 12
FRAME = 0x65400
DATA = FRAME + 16
CERT = 0x2EEDA0
EXE_LEN = 3082144

# Exactly the 7 behavior-setting bytes used by the measured MIN54-QUIET.
PATCH = {
    0x2750: 0x54,
    0x164D6: 0x54,
    0x216D2: 0xC4,
    0x216D3: 0x09,
    0x216D5: 0x50,
    0x216D6: 0xE4,
    0x216D7: 0x0C,
}
CHECKSUMS = (
    ('BOOT-1', 0x1000, 0x4400, 0x43FC, 0x2704FF56, 0x2704FF68, 0xFFFFFFEE),
    ('BRIDGE', 0x4400, 0x5000, 0x4FFC, 0x2093D4E7, 0x2093D4E7, 0),
    ('BOOT-2', 0x5000, 0x38000, 0x37FFC, 0xC86347B3, 0xCD8945B3, 0xFADA0200),
)


def must(ok, explanation):
    if not ok:
        raise RuntimeError('STOP: ' + explanation)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def checksum(b, start, end):
    return sum(row[0] for row in struct.iter_unpack('<I', b[start:end])) & 0xFFFFFFFF


def crc(b):
    return (~zlib.crc32(b)) & 0xFFFFFFFF


def xor8(b):
    v = 0
    for x in b:
        v ^= x
    return v


def pe_checksum_offset(b):
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    must(b[pe:pe+4] == b'PE\x00\x00', 'not a PE executable')
    return pe + 24 + 64


def pe_checksum(b):
    off = pe_checksum_offset(b)
    acc = 0
    for n in range(0, len(b), 2):
        if off <= n < off + 4:
            continue
        acc += b[n] | ((b[n+1] if n+1 < len(b) else 0) << 8)
        acc = (acc & 0xffff) + (acc >> 16)
    acc = (acc & 0xffff) + (acc >> 16)
    return ((acc & 0xffff) + len(b)) & 0xffffffff


def validate_pfs(p):
    must(len(p) == PFS_LEN, 'bad PFS length')
    embedded = p[PFS_EC_START:PFS_EC_START + EC_LEN]
    must(len(embedded) == EC_LEN, 'EC truncated in PFS')
    must(struct.unpack_from('<I', p, PFS_EC_CRC)[0] == crc(embedded), 'EC CRC failed')
    must(struct.unpack_from('<I', p, PFS_CRC)[0] == crc(p[16:-16]), 'PFS CRC failed')
    return embedded


def unpack_exe(e):
    must(len(e) == EXE_LEN, 'unexpected EXE size')
    must(pe_checksum(e) == struct.unpack_from('<I', e, pe_checksum_offset(e))[0],
         'PE CheckSum mismatch')
    count = struct.unpack_from('<I', e, FRAME)[0]
    must(0 < count and DATA + count + 16 <= CERT, 'invalid compressed PFS size')
    head = e[FRAME:DATA]
    tail = e[DATA + count:DATA + count + 16]
    must(xor8(head) == xor8(tail) == 0, 'PFS framing XOR mismatch')
    must(struct.unpack_from('<I', tail)[0] == count, 'PFS trailer length mismatch')
    obj = zlib.decompressobj()
    p = obj.decompress(e[DATA:DATA+count]) + obj.flush()
    must(obj.eof and not obj.unused_data, 'invalid or trailing zlib PFS data')
    validate_pfs(p)
    return p, head, tail


def compress_options(p):
    for mem in (8, 9, 7):
        c = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=15,
                             memLevel=mem, strategy=zlib.Z_DEFAULT_STRATEGY)
        yield f'zlib6/mem{mem}', c.compress(p) + c.flush()


def repack_exe(source_exe, pfs, old_head, old_tail):
    max_len = CERT - DATA - 16
    found = None
    for label, packed in compress_options(pfs):
        must(zlib.decompress(packed) == pfs, 'zlib roundtrip failed')
        print(f'Compression {label}: {len(packed)} / {max_len} bytes')
        if len(packed) <= max_len:
            found = label, packed
            break
    must(found is not None,
         'new zlib image DOES NOT FIT the EXE PFS container; nothing written. '
         'Do not truncate or overwrite certificate data.')
    label, packed = found
    head, tail = bytearray(old_head), bytearray(old_tail)
    struct.pack_into('<I', head, 0, len(packed))
    struct.pack_into('<I', tail, 0, len(packed))
    head[15] = xor8(head[:15])
    tail[15] = xor8(tail[:15])
    padding = CERT - (DATA + len(packed) + 16)
    blob = bytearray(source_exe[:FRAME] + head + packed + tail +
                     bytes(padding) + source_exe[CERT:])
    must(len(blob) == EXE_LEN and blob[CERT:] == source_exe[CERT:],
         'changed EXE size / certificate section')
    struct.pack_into('<I', blob, pe_checksum_offset(blob), pe_checksum(blob))
    must(struct.unpack_from('<I', blob, pe_checksum_offset(blob))[0] == pe_checksum(blob),
         'bad PE CheckSum after repack')
    extracted, _, _ = unpack_exe(bytes(blob))
    must(extracted == pfs, 'final EXE did not roundtrip to target PFS')
    print(f'Repacking: {label}, padding {padding} bytes')
    return bytes(blob)


def main():
    print('MIN54-QUIET + additive checksums: ONLY offline build, NO flash')
    must(not OUT_EC.exists() and not OUT_EXE.exists(),
         'output exists (refusing to overwrite)')
    candidates = [row for row in SOURCES if row[1].is_file() and row[2].is_file()]
    if not candidates:
        print('Checked source-file pairs:')
        for name, exe, ec, *_ in SOURCES:
            print(f'  {name}: EXE={exe.exists()} ({exe}); EC={ec.exists()} ({ec})')
        raise RuntimeError('STOP: no complete verified source pair found')

    # Prefer exact pair only. Abort on hash mismatch; don't silently fall back
    # to an unrelated file with the same path.
    kind, exe_path, ec_path, exe_sha, ec_sha = candidates[0]
    source_exe = exe_path.read_bytes()
    source_ec = ec_path.read_bytes()
    must(sha(source_exe) == exe_sha, f'unexpected source EXE SHA for {kind}')
    must(len(source_ec) == EC_LEN and sha(source_ec) == ec_sha,
         f'unexpected source EC SHA for {kind}')
    pfs, h, t = unpack_exe(source_exe)
    must(pfs[PFS_EC_START:PFS_EC_START + EC_LEN] == source_ec,
         'source EXE embeds DIFFERENT EC than raw source')
    print(f'Source: {kind}; EXE and EC SHA256 verified')

    raw = bytearray(source_ec)
    differences = []
    for offset, expected in PATCH.items():
        if raw[offset] != expected:
            differences.append((offset, raw[offset], expected))
            raw[offset] = expected
    must(raw[0x216D0:0x216DC] == bytes.fromhex('32 48 C4 09 41 50 E4 0C 4A 55 CC 10'),
         'wrong fan table')
    must(raw[0x2750] == raw[0x164D6] == 0x54, 'wrong Minimum Drive')
    must(sha(raw) == EXPECTED_HISTORICAL_QUIET_SHA,
         'reconstruction does NOT match historical tested MIN54-QUIET SHA256')
    print('Historical MIN54-QUIET reconstructed byte-for-byte: SHA256 OK')
    print('Applied functional changes: ' +
          ', '.join(f'0x{o:05X}:{a:02X}->{b:02X}' for o, a, b in differences))

    for name, start, end, word_at, old_word, new_word, pre_sum in CHECKSUMS:
        old = struct.unpack_from('<I', raw, word_at)[0]
        sm = checksum(raw, start, end)
        must(old == old_word, f'{name}: unexpected compensation word')
        must(sm == pre_sum, f'{name}: unexpected pre-patch sum 0x{sm:08X}')
        computed = (old - sm) & 0xFFFFFFFF
        must(computed == new_word, f'{name}: expected compensator differs')
        struct.pack_into('<I', raw, word_at, computed)
        must(checksum(raw, start, end) == 0, f'{name}: invalid corrected sum')
        print(f'{name:7s}: {sm:08X} -> 00000000, word {old:08X} -> {computed:08X}')
    final_ec = bytes(raw)
    changed_from_historical = [i for i,(a,b) in enumerate(zip(source_ec, final_ec)) if a!=b]
    if kind == 'MIN54-QUIET historical':
        must(changed_from_historical == [0x43FC, 0x37FFD, 0x37FFE, 0x37FFF],
             'unexpected changes from historical MIN54-QUIET')

    target_pfs = bytearray(pfs)
    target_pfs[PFS_EC_START:PFS_EC_START+EC_LEN] = final_ec
    struct.pack_into('<I', target_pfs, PFS_EC_CRC, crc(final_ec))
    struct.pack_into('<I', target_pfs, PFS_CRC, crc(target_pfs[16:-16]))
    must(validate_pfs(bytes(target_pfs)) == final_ec, 'target PFS validation failed')
    final_exe = repack_exe(source_exe, bytes(target_pfs), h, t)
    must(unpack_exe(final_exe)[0][PFS_EC_START:PFS_EC_START+EC_LEN] == final_ec,
         'EC extracted from final EXE does not match final EC')
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORK, prefix='min54q-build-') as folder:
        staged_ec = Path(folder)/OUT_EC.name
        staged_exe = Path(folder)/OUT_EXE.name
        staged_ec.write_bytes(final_ec)
        staged_exe.write_bytes(final_exe)
        must(staged_ec.read_bytes() == final_ec and staged_exe.read_bytes() == final_exe,
             'staging verification failed')
        os.replace(staged_ec, OUT_EC)
        os.replace(staged_exe, OUT_EXE)
    print('\n=== OFFLINE BUILD COMPLETED; NOT HARDWARE VALIDATED ===')
    print('Fan: MIN Drive 0x54; CPU table 2500 / 3300 / 4300 RPM unchanged')
    print('BOOT-1, BRIDGE, BOOT-2 checksums: all 0')
    print('PFS EC CRC / PFS CRC / PE checksum / zlib roundtrip: OK')
    print('NOTE: BIOSUtilities independent extraction not executed (not installed)')
    print('WARNING: Dell cryptographic signature is NOT valid; DO NOT FLASH YET')
    print(f'EC  SHA256 {sha(final_ec)}  {OUT_EC}')
    print(f'EXE SHA256 {sha(final_exe)}  {OUT_EXE}')

if __name__ == '__main__':
    main()