# One-shot confirmatory protocol

The runner validates all freeze hashes and contamination evidence before any
seed materialization. It rejects a pre-existing output root, derives a 256-bit
OS-random master secret, atomically writes a sealed seed manifest and then an
irreversible `STARTED` ledger. It prints only commitment and count. No reset,
overwrite, selective rerun or seed display is available.
