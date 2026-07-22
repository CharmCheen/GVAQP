# Install on Server

Target directory:

```text
/qiuyeqing/llama_prl/G-ARC/AEH_AQP_Agent_Handoff_Pack_v3
```

After placing `AEH_AQP_Agent_Handoff_Pack_v3.zip` in `/qiuyeqing/llama_prl/G-ARC`, run:

```bash
cd /qiuyeqing/llama_prl/G-ARC
unzip -q AEH_AQP_Agent_Handoff_Pack_v3.zip
cd AEH_AQP_Agent_Handoff_Pack_v3
tail -n +2 FILE_MANIFEST.csv | sed 's/,/  /' | sha256sum -c -
jq empty PROJECT_STATE.json
```

Expected result: every file reports `OK` and `jq` exits zero.

Then provide `10_NEXT_AGENT_MASTER_PROMPT.md` to Codex. The pack itself is guidance; Codex must reproduce server facts from the authoritative experiment directories before execution.

Do not overwrite v2 if it is already present. Preserve both versions for lineage.
