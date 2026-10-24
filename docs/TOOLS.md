# Offline analysis tools

Only two small Python programs are included in this public research edition. Neither needs access to the running EC or hardware registers.

## Read-only additive-checksum audit

```bash
python3 tools/audit_ec_additive_checksum.py --stock work/stock-EC-A14.bin
```

The input must be a locally acquired, authentic extracted **stock Dell A14 EC**. The script verifies its SHA-256, reconstructs three historical variants in memory, prints their combined and region-specific 32-bit little-endian sums and required compensation words, and makes **no writes**.

## Experimental M54FIX offline builder

```bash
python3 tools/build_min54quiet_from_available.py
```

The builder checks exact upstream inputs, reproduces the historical MIN54-QUIET image, patches the two compensation DWORDs, and validates hashes, separate EC sums, PFS/EC CRCs, compression round trips, and the PE checksum. Output files are produced in the untracked `work/` directory. It **does not flash**. The generated updater is **cryptographically unsigned/invalidly signed** and must not be treated as a verified safe flash payload.

This source code was developed for a particular **Dell Latitude E5420 A14** layout. It is not a general EC update library.

Other hardware-interacting SMM and thermal-stress tools from the private historical project are **deliberately excluded** from this clean public edition because of their model dependence and safety implications. The [historical research report](HISTORICAL_THERMAL_RESULTS.md) still documents the measured fan speeds.
