# Full-horizon execution

Each identity initializes an R2 environment and repeatedly constructs visible history, applies the frozen method, consumes admitted planning time, recomputes feasible actions, executes one action, and durably records it. It terminates only on STOP or deadline. The exact sidecar is called only after the approximate action has been selected.
