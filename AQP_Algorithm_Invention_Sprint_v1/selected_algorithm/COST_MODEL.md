# Cost model

For edge `a`, record

```text
c_a = model_load_share + decode_cpu + preprocess_cpu
      + synchronized_gpu_generation + parse_cpu + reconciliation_share
```

The optimizer scalar is synchronized GPU seconds, but the experiment reports
every component plus wall time. Logical calls are not substituted for seconds.
The prior dense unit ledger gives a descriptive mean generation cost of
15.410652 s and median 15.354899 s on an A800; the new A100 pilot must report
its own measurements and hardware difference.

For 70 registered windows, the strict 70% break-even requires mean complete
window cost below `3.47` dense-unit costs. Cold model load is reported once on
both sides or excluded only in an explicitly warm paired comparison. No energy
claim is made if hardware counters are unavailable.

