# About this public research edition

This is a deliberately **curated, anonymized, English-language technical edition** of a larger private research project on the Dell Latitude E5420 A14 Embedded Controller.

The original investigation ran during October 2026. Preserved numerical claims include image SHA-256 values, raw EC offsets, instruction addresses, the three additive checksum regions, controlled before/after firmware comparisons and actual fan-temperature measurements. Where a hardware purpose is inferred rather than directly observed, that distinction is stated.

**What is intentionally not included:**
- The original raw terminal transcript and command-paste logs.
- Personal local usernames, hostnames, home-directory names, and media mount paths.
- The private project's complete version-control history, including old commit author email metadata.
- Untested SMM writes, thermal-stress automation and uncurated experimental variants.
- Dell stock EC, system BIOS, PFS, EXE files, signed or unsigned flash update packages.
- The original untranslated 87-section (~200 KiB) disassembly diary and other long intermediate notebooks; the findings they support are condensed into the English side-research study.

The surviving primary evidence is retained in the private project for independent checking by its custodian. The public document set is **not** claimed to be an exhaustive line-by-line translation of those notebooks. The public release is not a vendor-endorsed update and does not establish safety of flashing.

## Publication procedure

**Do not set the original private repository to public.** Export or download only the **current files** of this curated snapshot, *without the private repository's Git history*, then create a brand new Git repository using those files. Never `git push --mirror` the original repository or push a branch that retains its earlier commits.

Licensing: publication as a readable source archive does **not** automatically grant an open-source reuse license. A final license for original research/code remains a decision for the copyright owner. The two Python programs in this edition contain no known embedded third-party GPL SMM code. Attribution to referenced external research remains in the papers.

For GitHub, see [the official repository visibility guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).
