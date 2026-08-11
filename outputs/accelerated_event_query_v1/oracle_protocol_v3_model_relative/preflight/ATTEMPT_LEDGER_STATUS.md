# Attempt Ledger Status

`COMPLETE_AUTHENTICATED_44_EVENTS`

The sealed runner will create one hash-chained JSONL ledger per execution shard.
Each event binds the exact call, input, attempt, and execution session. The
three hash-chained ledgers contain exactly 11 each of `PREPARED`,
`INFERENCE_STARTED`, `INFERENCE_COMPLETED`, and `ACCEPTED`, with no failure or
retry event. The analyzer joined every processed-input, generated-token, and
accepted-record hash to its raw record.
