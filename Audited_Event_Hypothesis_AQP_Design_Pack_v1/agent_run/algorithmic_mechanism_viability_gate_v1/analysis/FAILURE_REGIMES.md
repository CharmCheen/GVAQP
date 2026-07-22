# Failure Regimes

Negative and null cells are retained rather than averaged away. Exploration is broadly negative in synthetic and S1 regimes. The Suite B `merge_ambiguity` manipulation is inactive in generator code and all three nominal levels produce identical per-seed outputs; it cannot establish a barrier-frequency effect. The 20 weakest cells are:

| suite            | comparison        |   target_auroc |   duration |   candidate_recall |   false_burden |   fragmentation |   mean_effect |   ci95_low |   ci95_high |
|:-----------------|:------------------|---------------:|-----------:|-------------------:|---------------:|----------------:|--------------:|-----------:|------------:|
| A_SATURATION     | Delta_exploration |           0.55 |          8 |                1   |            0.2 |               1 |     -0.837341 |  -0.842382 |   -0.832301 |
| A_SATURATION     | Delta_exploration |           0.55 |          8 |                1   |            0.5 |               1 |     -0.836328 |  -0.841358 |   -0.831298 |
| A_SATURATION     | Delta_exploration |           0.55 |          4 |                1   |            0.2 |               1 |     -0.623817 |  -0.636586 |   -0.611048 |
| A_SATURATION     | Delta_exploration |           0.55 |          4 |                1   |            0.5 |               1 |     -0.613061 |  -0.626729 |   -0.599393 |
| A_SATURATION     | Delta_exploration |           0.55 |          4 |                1   |            0.8 |               1 |     -0.532825 |  -0.546596 |   -0.519054 |
| A_SATURATION     | Delta_exploration |           0.65 |          8 |                1   |            0.2 |               1 |     -0.438155 |  -0.450001 |   -0.426309 |
| C_ROBUSTNESS     | Delta_exploration |           0.65 |          2 |                1   |            0.5 |               1 |     -0.411212 |  -0.426129 |   -0.396294 |
| A_SATURATION     | Delta_exploration |           0.55 |          2 |                1   |            0.2 |               1 |     -0.407272 |  -0.420506 |   -0.394037 |
| A_SATURATION     | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               1 |     -0.398278 |  -0.411066 |   -0.385491 |
| C_ROBUSTNESS     | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               1 |     -0.361982 |  -0.378956 |   -0.345008 |
| A_SATURATION     | Delta_exploration |           0.65 |          8 |                1   |            0.5 |               1 |     -0.360461 |  -0.371995 |   -0.348927 |
| C_ROBUSTNESS     | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               1 |     -0.359255 |  -0.375848 |   -0.342662 |
| C_ROBUSTNESS     | Delta_exploration |           0.55 |          2 |                1   |            0.2 |               1 |     -0.345295 |  -0.361233 |   -0.329356 |
| A_SATURATION     | Delta_exploration |           0.55 |          2 |                1   |            0.8 |               1 |     -0.34398  |  -0.356503 |   -0.331456 |
| C_ROBUSTNESS     | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               1 |     -0.337837 |  -0.353317 |   -0.322356 |
| C_ROBUSTNESS     | Delta_exploration |           0.65 |          2 |                1   |            0.5 |               1 |     -0.306942 |  -0.319604 |   -0.29428  |
| B_COUNTERFACTUAL | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               2 |     -0.305832 |  -0.321033 |   -0.290632 |
| B_COUNTERFACTUAL | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               2 |     -0.305832 |  -0.321033 |   -0.290632 |
| B_COUNTERFACTUAL | Delta_exploration |           0.55 |          2 |                1   |            0.5 |               2 |     -0.305832 |  -0.321033 |   -0.290632 |
| C_ROBUSTNESS     | Delta_exploration |           0.55 |          2 |                0.8 |            0.5 |               1 |     -0.304335 |  -0.319592 |   -0.289078 |
