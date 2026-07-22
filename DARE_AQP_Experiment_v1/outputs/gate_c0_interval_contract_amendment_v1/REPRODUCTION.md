# Reproduction

From the repository root:

```bash
python garc_eval/interval_oracle_contract_amendment_v1/derive.py
python garc_eval/interval_oracle_contract_amendment_v1/build_contract.py
python garc_eval/interval_oracle_contract_amendment_v1/audit_amendment.py
```

These commands read only frozen C0/reference artifacts. They must not read a
physical interval response or load a VLM.
