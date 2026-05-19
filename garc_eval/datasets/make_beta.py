"""Generate synthetic Beta data matching the SUPG paper's simulation setup.

A(x) ~ Beta(alpha, beta)   — proxy score
O(x) ~ Bernoulli(A(x))     — oracle label
"""

import argparse
import pathlib

import numpy as np
import pandas as pd


def generate_beta_dataset(
    n: int = 1_000_000,
    alpha: float = 0.01,
    beta: float = 1.0,
    seed: int = 0,
    output_path: str | None = None,
) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    proxy_score = rng.beta(alpha, beta, size=n).astype(np.float32)
    label = rng.binomial(1, proxy_score).astype(np.int8)
    df = pd.DataFrame({
        "id": np.arange(n, dtype=np.int64),
        "proxy_score": proxy_score,
        "label": label,
    })
    tpr = df["label"].mean()
    print(f"Beta({alpha}, {beta}) | n={n} | seed={seed} | true positive rate = {tpr:.6f}")
    if output_path:
        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")
    return df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Beta dataset for SUPG experiments")
    parser.add_argument("--n", type=int, default=1_000_000)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--beta", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()
    generate_beta_dataset(args.n, args.alpha, args.beta, args.seed, args.output)


if __name__ == "__main__":
    main()
