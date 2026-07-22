# A4 JOINT error semantics

JOINT uses the A1 common `k=JOINT` sign for every applicable family at a
decision/trajectory. Its A2 target identity and draw index are canonically
`JOINT` and `0`, so target-specific A2 fields cannot accidentally make signs
differ by family. It does not reuse a common uniform: each family has its
own A4 subkey. Kernel probabilities are recomputed from the current simulated
branch state before each action. The fixed family order and atomic transition
boundary prevent dict-order dependence and half-updated state visibility.
