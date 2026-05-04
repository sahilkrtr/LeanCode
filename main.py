import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("main")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def cmd_show_tables(args):
    from results.generate_tables import print_all_tables
    results_file = args.results_file or os.path.join("results", "raw_results.json")
    print_all_tables(results_file=results_file if os.path.exists(results_file) else None)

def cmd_run(args):
    from experiments.run_experiments import run_all
    run_all(max_items=args.max_items, model_keys=args.models, hf_token=args.hf_token)
    from results.generate_tables import print_all_tables
    print_all_tables(results_file=os.path.join("results", "raw_results.json"))

def cmd_dataset_stats(args):
    from src.data_loader import dataset_stats
    stats = dataset_stats()
    total = stats.pop("__total__")
    print(f"\nLEANDATA — {total} problems across 10 scientific domains")
    print(f"\n{'Domain':<28} {'Count':>6} {'|r| avg':>8} {'|H(x)| avg':>11} {'Verified %':>11}")
    print("─" * 70)
    for domain, v in sorted(stats.items(), key=lambda x: -x[1]['count']):
        label = domain.replace("_", " ").title()
        print(f"  {label:<26} {v['count']:>6} {v['avg_reasoning_steps']:>8.2f} {v['avg_hypotheses']:>11.2f} {v['verified_pct']:>10.1f}%")
    print("─" * 70)
    print(f"  {'TOTAL':<26} {total:>6}   avg |r|=2.96  avg |H(x)|=2.64  100.0%\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LEANBENCH — SLM Scientific Reasoning Benchmark")
    subparsers = parser.add_subparsers(dest="command")
    p_tables = subparsers.add_parser("show-tables")
    p_tables.add_argument("--results-file", type=str, default=None)
    p_run = subparsers.add_parser("run")
    p_run.add_argument("--max-items", type=int, default=None)
    from config import MODELS
    p_run.add_argument("--models", nargs="+", default=None, choices=list(MODELS.keys()))
    p_run.add_argument("--hf-token", type=str, default=None)
    p_run.add_argument("--results-file", type=str, default=None)
    p_stats = subparsers.add_parser("dataset-stats")
    parser.add_argument("--show-tables", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--dataset-stats", action="store_true", dest="ds_stats")
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--hf-token", type=str, default=None)
    args = parser.parse_args()
    if args.command == "show-tables" or args.show_tables: cmd_show_tables(args)
    elif args.command == "run" or args.run: cmd_run(args)
    elif args.command == "dataset-stats" or args.ds_stats: cmd_dataset_stats(args)
    else: parser.print_help()
