"""Metrics with uncertainty: AUROC, recall at a fixed false-positive rate, bootstrap intervals."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve


def auroc(y, s) -> float:
    return float(roc_auc_score(y, s))


def tpr_at_fpr(y, s, fpr_target: float = 0.01) -> float:
    fpr, tpr, _ = roc_curve(y, s)
    return float(np.interp(fpr_target, fpr, tpr))


def bootstrap_ci(values, stat=np.mean, n: int = 2000, alpha: float = 0.05, seed: int = 0):
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    boots = [stat(rng.choice(v, len(v), replace=True)) for _ in range(n)]
    return float(stat(v)), float(np.quantile(boots, alpha / 2)), float(np.quantile(boots, 1 - alpha / 2))


def bootstrap_auroc(y, s, n: int = 1000, seed: int = 0):
    y, s = np.asarray(y), np.asarray(s)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            out.append(roc_auc_score(y[i], s[i]))
    return auroc(y, s), float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))
