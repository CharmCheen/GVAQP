# P1-B full-repository engineering validation

`FULL_REPO_TESTS = PASS`

- Command: `PYTHONPATH=src:scripts:tests:experiments pytest -q --import-mode=importlib`
- Natural completion exit code: `0`
- Result: `706 passed, 1 warning in 127.00s`
- Warning: existing Python fork deprecation warning in `test_oracle_v3_full_grid_hiding.py`; no test failure.
- P1-B focused tests: `15 passed`.
- Human annotation records at validation: `0`.

The initial full-suite run completed with 703 passes and three pre-existing engineering compatibility failures. Minimal fixes restored the legacy scan CLI manifest interface and corrected the vendored SUPG path/unnecessary `feather` import. No P1-B scientific protocol, pair membership, geometry definition, query definition, annotation guide, or outcome analysis was changed.
