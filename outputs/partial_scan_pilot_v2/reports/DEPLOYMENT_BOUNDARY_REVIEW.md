# V2 Deployment-Boundary Review

## Scope and evidence

This is a configuration review only. It does not run chroot, sentinel, UID,
`/proc`, permission, or attack-style tests.

Reviewed evidence:

- `src/garc_eval/partial_scan_v2/isolated_policy_client.py`;
- `src/garc_eval/partial_scan_v2/config.py`;
- repository search for container, service, orchestration, or deployment
  manifests applicable to `partial_scan_v2`.

No production launch manifest, mount specification, service definition, or
orchestrator configuration for the v2 policy process is present in the
worktree.

## Findings

| Required deployment property | Direct evidence | Result |
|---|---|---|
| Policy mounts only its package | No mount specification exists; the development child executes a source file in the shared repository. | NOT ESTABLISHED |
| Benchmark root invisible to Policy | No filesystem namespace or mount rule is specified. | NOT ESTABLISHED |
| Reference and unscanned outputs held only by Evaluator | The public API omits them, but no deployment filesystem boundary proves policy cannot read them. | NOT ESTABLISHED |
| Environment whitelist | The launcher passes only `PYTHONUNBUFFERED`, `POLICY_RUN_ID`, and `POLICY_PROTOCOL_VERSION`. | PASS (application launcher only) |
| No extra policy network entry | No network policy is specified. | NOT ESTABLISHED |
| Only agreed IPC | The application launch provides stdin/stdout JSONL pipes and closes inherited FDs. A deployment-level channel policy is absent. | PARTIAL |
| Different policy/evaluator identities | The development launcher does not set a separate user or group; the child inherits the evaluator identity. | FAIL |

## Decision

```text
POLICY_CAPABILITY_ISOLATION = NOT_ESTABLISHED
APPLICATION_PROCESS_BOUNDARY = ESTABLISHED
PUBLIC_API_DATA_MINIMIZATION = PASS
METHOD_SELECTION = PROHIBITED
```

The strongest supported conclusion is that the checked launcher is suitable for
application-protocol testing only, not for the claimed capability boundary. The
main competing explanation—that an untracked or external production deployment
enforces the required boundary—cannot be evaluated from this workspace.

## Required next evidence

Provide the actual production deployment definition (for example an
orchestrator manifest, service unit plus mount setup, or container image/run
configuration) showing the policy package mount, evaluator-only data mounts,
distinct identities, environment allowlist, no network path, and sole IPC
channel. Review that configuration before freezing
`POLICY_CAPABILITY_ISOLATION = PASS`.
