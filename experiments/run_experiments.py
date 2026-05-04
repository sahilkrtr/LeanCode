import os
import sys
import json
import logging
import shutil
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MODELS, RESULTS_DIR, HYPERPARAMS, CHECKPOINTS_DIR
from src.data_loader import load_all, split_train_test
from src.model_inference import HFInferenceModel
from src.evaluator import (
    run_full_inference_pass,
    evaluate_model_all_settings,
    evaluate_domain_wise,
    evaluate_ablation,
)
from src.rl_training import RLTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
os.makedirs(RESULTS_DIR, exist_ok=True)

def build_few_shot_pool(all_items: List[Dict]) -> Dict[str, List[Dict]]:
    pool = {}
    by_domain: Dict[str, List] = {}
    for item in all_items:
        by_domain.setdefault(item.get("lean_domain", "physics"), []).append(item)
    for domain, items in by_domain.items():
        verified = [x for x in items if x.get("verification_result") in ("symbolically_verified", "verified", True)]
        pool[domain] = (verified or items)[:3]
    return pool

def run_all(
    max_items: Optional[int] = None,
    model_keys: Optional[List[str]] = None,
    hf_token: Optional[str] = None,
) -> Dict:
    # Hard check for Lean 4
    if not (shutil.which("lean") or shutil.which("lake")):
        logger.error("Lean 4 binary not found. Please install elan/lean4 for formal RL training.")
        sys.exit(1)

    keys = model_keys or list(MODELS.keys())
    all_items = load_all()
    train_items, _ = split_train_test(all_items)
    few_shot_pool = build_few_shot_pool(train_items)
    all_results: Dict = {}

    for model_key in keys:
        logger.info(f"\n{'='*60}\nModel: {model_key}\n{'='*60}")
        model = HFInferenceModel(model_key, hf_token=hf_token)

        # 1. RL Training (Formal only)
        trainer = RLTrainer(model_key, hf_token=hf_token)
        rl_result = trainer.train(train_items[:50] if max_items else train_items)
        
        # 2. Base Inference Pass
        logger.info("Running base inference pass …")
        base_cache = run_full_inference_pass(all_items, model, model_key, few_shot_pool=few_shot_pool, max_items=max_items)
        
        # 3. RL Inference Pass
        ckpt_path = os.path.join(CHECKPOINTS_DIR, f"{model_key}_rl_weights.pt")
        rl_cache = None
        if os.path.exists(ckpt_path):
            logger.info("Running RL-tuned inference pass …")
            model.load_checkpoint(ckpt_path)
            rl_cache = run_full_inference_pass(all_items, model, model_key, few_shot_pool=few_shot_pool, max_items=max_items)

        # 4. Evaluation
        logger.info("Scoring all benchmarks …")
        main_res = evaluate_model_all_settings(all_items, model, model_key, few_shot_pool=few_shot_pool, max_items=max_items, _cache=base_cache, _rl_cache=rl_cache)
        domain_res = evaluate_domain_wise(all_items, model, model_key, few_shot_pool=few_shot_pool, max_per_domain=max_items, _cache=base_cache, _rl_cache=rl_cache)
        ablation_res = evaluate_ablation(all_items, model, model_key, few_shot_pool=few_shot_pool, max_items=max_items, _cache=base_cache, _rl_cache=rl_cache)

        all_results[model_key] = {"main": main_res, "domain": domain_res, "ablation": ablation_res, "rl_training": rl_result}
        out_path = os.path.join(RESULTS_DIR, f"results_{model_key.replace('/', '_')}.json")
        with open(out_path, "w") as f: json.dump(all_results[model_key], f, indent=2, default=str)

    with open(os.path.join(RESULTS_DIR, "raw_results.json"), "w") as f: json.dump(all_results, f, indent=2, default=str)
    return all_results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--hf-token", type=str, default=None)
    args = parser.parse_args()
    run_all(max_items=args.max_items, model_keys=args.models, hf_token=args.hf_token)
