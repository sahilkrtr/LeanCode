"""
Metrics (all in %):
  VA  — Verification Accuracy   = fraction with π ∈ P_valid
  FR  — Falsification Rate      = fraction with ∃x': ¬φ(x')
  SC  — Structural Consistency  = fraction with well-formed (r, H(x), φ(x))
  AC  — Alignment Consistency   = fraction with r ↔ H(x) ↔ φ(x)
  E2E — End-to-End success      = fraction with VA ∨ FR
  Avg — mean of the five metrics
"""
from typing import Dict, List, Optional, Tuple


MetricsDict = Dict[str, float]


def compute_metrics(results: List[Dict[str, bool]]) -> MetricsDict:
    """
    Aggregate per-instance evaluation results into dataset-level metrics.

    Parameters
    ----------
    results : list of dicts with keys 'va', 'fr', 'sc', 'ac', 'e2e' (bool)

    Returns
    -------
    dict with keys VA, FR, SC, AC, E2E, Avg (all in %)
    """
    if not results:
        return {"VA": 0.0, "FR": 0.0, "SC": 0.0, "AC": 0.0, "E2E": 0.0, "Avg": 0.0}

    n = len(results)
    va  = 100.0 * sum(r["va"]  for r in results) / n
    fr  = 100.0 * sum(r["fr"]  for r in results) / n
    sc  = 100.0 * sum(r["sc"]  for r in results) / n
    ac  = 100.0 * sum(r["ac"]  for r in results) / n
    e2e = 100.0 * sum(r["e2e"] for r in results) / n
    avg = (va + fr + sc + ac + e2e) / 5.0

    return {
        "VA":  round(va,  1),
        "FR":  round(fr,  1),
        "SC":  round(sc,  1),
        "AC":  round(ac,  1),
        "E2E": round(e2e, 1),
        "Avg": round(avg, 1),
    }


def compute_compute_stats(
    elapsed_seconds: float,
    num_tokens: int,
    peak_memory_gb: float,
    gpu_hours: float,
) -> Dict[str, float]:
    """Compute throughput (Tok/s), memory (GB), GPU-hrs."""
    tok_s = round(num_tokens / max(elapsed_seconds, 1.0), 0)
    return {
        "Tok/s": tok_s,
        "Mem":   round(peak_memory_gb, 1),
        "GPU-hrs": round(gpu_hours, 1),
    }


def aggregate_domain_metrics(
    domain_results: Dict[str, List[Dict[str, bool]]]
) -> Dict[str, MetricsDict]:
    """Compute per-domain metrics from a dict of domain → instance results."""
    return {d: compute_metrics(v) for d, v in domain_results.items()}



