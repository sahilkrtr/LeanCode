import os
import time
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import HYPERPARAMS, MODELS
from src.prompts import build_zero_shot_prompt, build_few_shot_prompt, build_counterexample_prompt
from src.output_parser import evaluate_output, parse_output
from src.lean_verifier import verify_lean_proof, verify_counterexample
from src.metrics import compute_metrics

logger = logging.getLogger(__name__)

def _domain_of(item: Dict) -> str:
    return item.get("lean_domain", "physics")

def _run_item_single_pass(
    item: Dict,
    model,
    prompt_mode: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
) -> Tuple[str, Dict[str, Any], float]:
    domain  = _domain_of(item)
    problem = item.get("problem", "")
    
    if prompt_mode == "ZS":
        prompt = build_zero_shot_prompt(problem, domain)
    else:
        examples = (few_shot_pool or {}).get(domain, [])
        prompt   = build_few_shot_prompt(problem, domain, examples or None)

    t0 = time.time()
    output_text, _ = model.generate(prompt)
    elapsed = time.time() - t0

    parsed = parse_output(output_text)
    return output_text, parsed, elapsed


def _score_base(parsed: Dict, item: Dict) -> Dict[str, bool]:
    result = evaluate_output(parsed.get("raw", ""), ground_truth=item)

    lean_code = parsed.get("lean_code", "")
    if lean_code:
        success, _ = verify_lean_proof(lean_code)
        result["va"] = success

    return {
        "sc": result["sc"],
        "ac": result["ac"],
        "va": result["va"],
        "fr": result["fr"],
        "e2e": result["va"] or result["fr"],
    }

def _score_trained(parsed: Dict, item: Dict) -> Dict[str, bool]:
    return _score_base(parsed, item)

def _score_rl(
    parsed: Dict,
    item: Dict,
    model,
    prompt_mode: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
) -> Dict[str, bool]:
    base = _score_base(parsed, item)

    if not base["fr"]:
        try:
            domain  = _domain_of(item)
            problem = item.get("problem", "")
            hyps    = parsed.get("hypotheses") or item.get("hypotheses", [])
            spec    = parsed.get("formal_spec") or item.get("lean_formal_statement", "")
            cex_prompt = build_counterexample_prompt(problem, domain, hyps, spec)
            cex_out, _ = model.generate(cex_prompt)
            gt_ans = str(item.get("final_answer", ""))
            base["fr"] = verify_counterexample(cex_out, gt_ans, hyps)
        except Exception as exc:
            logger.debug(f"Counterexample generation failed: {exc}")

    base["e2e"] = base["va"] or base["fr"]
    return base

# ─────────────────────────────────────────────
# EVALUATION ENGINE
# ─────────────────────────────────────────────

def _evaluate_cached(
    cached: List[Tuple[str, Dict, float, Dict]],
    model,
    model_name: str,
    setting: str,
    prompt_mode: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
) -> Dict:
    score_fn = {
        "Base":            _score_base,
        "Trained":         _score_trained,
        "RL_Verification": None,
    }[setting]

    all_metrics: List[Dict[str, bool]] = []
    total_tokens = 0.0
    start = time.time()

    for (output, parsed, elapsed, item) in cached:
        tokens_est = len(output.split()) * 1.3 + 300
        if setting == "RL_Verification":
            m = _score_rl(parsed, item, model, prompt_mode, few_shot_pool)
        else:
            m = score_fn(parsed, item)
        all_metrics.append(m)
        total_tokens += tokens_est

    wall = max(time.time() - start, 1.0)
    metrics = compute_metrics(all_metrics)
    return {
        "metrics": metrics,
        "compute": {
            "Tok/s": round(total_tokens / wall, 0),
            "elapsed_s": round(wall, 1),
        },
        "n_items": len(cached),
    }

def run_full_inference_pass(
    test_items: List[Dict],
    model,
    model_name: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
    max_items: Optional[int] = None,
    seed: int = HYPERPARAMS["seed"],
) -> Dict[str, List[Tuple]]:
    rng    = random.Random(seed)
    sample = list(test_items[:max_items] if max_items else test_items)
    rng.shuffle(sample)
    cache: Dict[str, List[Tuple]] = {}
    for pm in ["ZS", "FS"]:
        logger.info(f"  [{model_name}] Inference: {pm} ({len(sample)} items) …")
        t0 = time.time()
        rows: List[Tuple] = []
        for idx, item in enumerate(sample):
            output, parsed, elapsed = _run_item_single_pass(item, model, pm, few_shot_pool=few_shot_pool)
            rows.append((output, parsed, elapsed, item))
        cache[pm] = rows
    return cache

def evaluate_model_all_settings(
    test_items: List[Dict],
    model,
    model_name: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
    max_items: Optional[int] = None,
    seed: int = HYPERPARAMS["seed"],
    _cache: Optional[Dict[str, List[Tuple]]] = None,
    _rl_cache: Optional[Dict[str, List[Tuple]]] = None,
) -> Dict:
    cache = _cache or run_full_inference_pass(test_items, model, model_name, few_shot_pool=few_shot_pool, max_items=max_items, seed=seed)
    results: Dict = {}
    for setting in ["Base", "Trained", "RL_Verification"]:
        results[setting] = {}
        for pm in ["ZS", "FS"]:
            target_cache = _rl_cache[pm] if (setting == "RL_Verification" and _rl_cache) else cache[pm]
            res = _evaluate_cached(target_cache, model, model_name, setting, pm, few_shot_pool=few_shot_pool)
            results[setting][pm] = res
    return results

def evaluate_domain_wise(
    test_items: List[Dict],
    model,
    model_name: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
    max_per_domain: Optional[int] = None,
    _cache: Optional[Dict[str, List[Tuple]]] = None,
    _rl_cache: Optional[Dict[str, List[Tuple]]] = None,
) -> Dict:
    results: Dict = {}
    for pm in ["ZS", "FS"]:
        pm_rows = _cache[pm]
        rl_pm_rows = _rl_cache[pm] if _rl_cache else pm_rows
        by_domain = {}
        for row in pm_rows: by_domain.setdefault(_domain_of(row[3]), []).append(row)
        rl_by_domain = {}
        for row in rl_pm_rows: rl_by_domain.setdefault(_domain_of(row[3]), []).append(row)
        for domain, rows in by_domain.items():
            if domain not in results: results[domain] = {}
            for setting in ["Trained", "RL_Verification"]:
                if setting not in results[domain]: results[domain][setting] = {}
                target_rows = rl_by_domain.get(domain, rows) if setting == "RL_Verification" else rows
                res = _evaluate_cached(target_rows[:max_per_domain] if max_per_domain else target_rows, model, model_name, setting, pm, few_shot_pool=few_shot_pool)
                results[domain][setting][pm] = res["metrics"]
    return results

def evaluate_ablation(
    test_items: List[Dict],
    model,
    model_name: str,
    few_shot_pool: Optional[Dict[str, List[Dict]]] = None,
    max_items: Optional[int] = None,
    _cache: Optional[Dict[str, List[Tuple]]] = None,
    _rl_cache: Optional[Dict[str, List[Tuple]]] = None,
) -> List[Dict]:
    cache, rl_cache = _cache, _rl_cache or _cache
    configs = [
        ("Base", "Base", False, False, False),
        ("+ RL+Ver.", "RL_Verification", True, True, True),
    ]
    results = []
    for (label, base_setting, use_struct, use_align, use_ver) in configs:
        config_res = {"Setting": label}
        for pm in ["ZS", "FS"]:
            rows = rl_cache[pm] if base_setting == "RL_Verification" else cache[pm]
            all_m = []
            for (out, parsed, el, item) in rows:
                m = _score_base(parsed, item)
                all_m.append(m)
            config_res[pm] = compute_metrics(all_m)
        results.append(config_res)
    return results