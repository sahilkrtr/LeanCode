import json
import os
import random
from typing import Dict, List, Optional, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, HYPERPARAMS


_FILE_TO_DOMAIN: Dict[str, str] = {
    "atkins.json":   "chemistry",
    "class.json":    "physics",
    "fund.json":     "physics",
    "chemmc.json":   "physics",
    "matter.json":   "chemistry",
    "stat.json":     "probability",
    "calculus.json": "physics",
    "diff.json":     "differential_equations",
    "thermo.json":   "chemistry",
    "quan.json":     "physics",
}

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "statistics":     ["mean", "variance", "standard deviation", "normal distribution",
                       "confidence interval", "hypothesis test", "regression", "correlation",
                       "sample", "population", "chi-square", "t-test", "anova"],
    "geometry":       ["triangle", "circle", "sphere", "volume", "area", "perimeter",
                       "radius", "diameter", "polygon", "coordinate", "angle", "distance"],
    "linear_algebra": ["matrix", "vector", "eigenvalue", "eigenvector", "determinant",
                       "linear transformation", "dot product", "cross product", "inner product",
                       "rank", "span", "basis", "orthogonal", "norm"],
}

_CANONICAL_DOMAINS = [
    "physics", "chemistry", "probability", "calculus",
    "differential_equations", "statistics", "thermodynamics",
    "quantum_mechanics", "geometry", "linear_algebra",
]


def _detect_domain(item: Dict, base_domain: str) -> str:
    """Refine domain label using keyword heuristics."""
    text = (item.get("problem", "") + " " + item.get("domain", "")).lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return domain
    explicit = item.get("domain", "").lower()
    if explicit:
        # Normalise dataset's own domain field
        for canon in _CANONICAL_DOMAINS:
            if canon.replace("_", " ") in explicit or canon in explicit:
                return canon
    return base_domain


def load_all(data_dir: str = DATA_DIR, seed: int = HYPERPARAMS["seed"]) -> List[Dict]:
    """
    Load every JSON file in *data_dir*, assign canonical domain labels,
    and return all records as a flat list.  Each record gains a
    ``lean_domain`` key with the paper's canonical domain name.
    """
    all_items: List[Dict] = []
    for fname, base_domain in _FILE_TO_DOMAIN.items():
        fpath = os.path.join(data_dir, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r") as f:
            records = json.load(f)
        for item in records:
            item = dict(item)
            item["lean_domain"] = _detect_domain(item, base_domain)
            item["source_file"] = fname
            all_items.append(item)

    # Deduplicate by problem_id if present
    seen_ids = set()
    unique: List[Dict] = []
    for item in all_items:
        pid = item.get("problem_id", id(item))
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique.append(item)

    rng = random.Random(seed)
    rng.shuffle(unique)
    return unique


def load_by_domain(data_dir: str = DATA_DIR) -> Dict[str, List[Dict]]:
    """Return a dict mapping canonical domain → list of problems."""
    all_items = load_all(data_dir)
    by_domain: Dict[str, List[Dict]] = {}
    for item in all_items:
        d = item["lean_domain"]
        by_domain.setdefault(d, []).append(item)
    return by_domain


def get_few_shot_examples(
    domain: str,
    data_dir: str = DATA_DIR,
    n: int = 1,
    exclude_ids: Optional[List] = None,
    seed: int = HYPERPARAMS["seed"],
) -> List[Dict]:
    """
    Sample *n* verified examples for *domain* to use as few-shot demonstrations.
    """
    by_domain = load_by_domain(data_dir)
    pool = [
        x for x in by_domain.get(domain, [])
        if x.get("verification_result") in ("symbolically_verified", "verified", True)
        and (exclude_ids is None or x.get("problem_id") not in exclude_ids)
    ]
    if not pool:
        pool = by_domain.get(domain, [])
    rng = random.Random(seed)
    return rng.sample(pool, min(n, len(pool)))


def split_train_test(
    all_items: List[Dict],
    test_ratio: float = 0.2,
    seed: int = HYPERPARAMS["seed"],
) -> Tuple[List[Dict], List[Dict]]:
    """80/20 train-test split used for evaluation."""
    rng = random.Random(seed)
    items = list(all_items)
    rng.shuffle(items)
    n_test = max(1, int(len(items) * test_ratio))
    return items[n_test:], items[:n_test]


def dataset_stats(data_dir: str = DATA_DIR) -> Dict:
    """Print dataset statistics."""
    by_domain = load_by_domain(data_dir)
    stats: Dict = {}
    total = 0
    for domain, items in by_domain.items():
        n = len(items)
        total += n
        avg_r = (
            sum(len(x.get("reasoning_steps", [])) for x in items) / max(1, n)
        )
        avg_h = (
            sum(len(x.get("hypotheses", [])) for x in items) / max(1, n)
        )
        verified = sum(
            1 for x in items
            if x.get("verification_result") in ("symbolically_verified", "verified", True)
        )
        stats[domain] = {
            "count": n,
            "avg_reasoning_steps": round(avg_r, 2),
            "avg_hypotheses": round(avg_h, 2),
            "verified_pct": round(100 * verified / max(1, n), 1),
        }
    stats["__total__"] = total
    return stats


if __name__ == "__main__":
    s = dataset_stats()
    print(f"\nLEANDATA — total problems: {s.pop('__total__')}")
    print(f"{'Domain':<25} {'Count':>6} {'|r|':>6} {'|H(x)|':>8} {'Verified':>9}")
    print("-" * 60)
    for d, v in s.items():
        print(
            f"{d:<25} {v['count']:>6} {v['avg_reasoning_steps']:>6.2f} "
            f"{v['avg_hypotheses']:>8.2f} {v['verified_pct']:>8.1f}%"
        )
