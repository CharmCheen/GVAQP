# Failed Pre-Inference Two-GPU Acquisition Attempt [6,7]

Status: `FAILED_PREINFERENCE_NONEXCLUSIVE_TOPOLOGY`.

The first dynamic allocator revision accepted GPU 6 based on free capacity but
did not require low *used* memory.  The runner's final authoritative
exclusivity gate correctly rejected GPU 6 at 9,096 MiB used, before model
load.  GPU 7 was idle.  No model load, raw oracle output, parsed semantic
outcome, or checkpoint occurred.

`semantic_output_exposure = NONE`.  The allocator successor requires both no
compute context and used memory at or below the frozen 16 MiB idle threshold.
