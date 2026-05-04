import os
import sys
import json
import argparse
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tabulate import tabulate
    _TABULATE = True
except ImportError:
    _TABULATE = False

def _fmt(v: Any, bold_threshold: Optional[float] = None) -> str:
    if isinstance(v, float):
        s = f"{v:.1f}"
        return s
    return str(v)


def _row(vals: List[Any]) -> List[str]:
    return [_fmt(v) for v in vals]


def _print_table(headers: List[str], rows: List[List], title: str) -> None:
    print(f"\n{'─'*90}")
    print(f"  {title}")
    print(f"{'─'*90}")
    if _TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="rounded_grid", floatfmt=".1f"))
    else:
        # Fallback pretty-printer
        col_w = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) + 2
                 for i, h in enumerate(headers)]
        header_line = "  ".join(str(h).ljust(w) for h, w in zip(headers, col_w))
        print(header_line)
        print("-" * len(header_line))
        for row in rows:
            print("  ".join(str(c).ljust(w) for c, w in zip(row, col_w)))
    print()


# ── results ─────────────────────────────────────────────────────

def print_table2(data: Dict) -> None:
    headers = [
        "Model", "Setting",
        "ZS VA", "ZS FR", "ZS SC", "ZS AC", "ZS E2E", "ZS Avg",
        "FS VA", "FS FR", "FS SC", "FS AC", "FS E2E", "FS Avg",
        "Tok/s", "Mem(GB)", "GPU-hrs",
    ]
    rows = []
    setting_labels = {
        "Base": "Base (Prompting Only)",
        "Trained": "+Trained (w/o RL)",
        "RL_Verification": "+RL+Verification",
    }
    for model_key, model_data in data.items():
        for setting_key, setting_label in setting_labels.items():
            sd = model_data.get(setting_key, {})
            zs = sd.get("ZS", {})
            fs = sd.get("FS", {})
            comp = model_data.get("compute", {})
            gpu_key = {
                "Base": "GPU-hrs_base",
                "Trained": "GPU-hrs_trained",
                "RL_Verification": "GPU-hrs_rl",
            }[setting_key]
            row = [
                model_key, setting_label,
                zs.get("VA", "-"), zs.get("FR", "-"), zs.get("SC", "-"),
                zs.get("AC", "-"), zs.get("E2E", "-"), zs.get("Avg", "-"),
                fs.get("VA", "-"), fs.get("FR", "-"), fs.get("SC", "-"),
                fs.get("AC", "-"), fs.get("E2E", "-"), fs.get("Avg", "-"),
                comp.get("Tok/s", "-"), comp.get("Mem", "-"), comp.get(gpu_key, "-"),
            ]
            rows.append(row)

    _print_table(headers, rows, "TABLE 2 — Main Results on LEANDATA")


def print_table3(data: Dict) -> None:
    headers = [
        "Domain", "Setting",
        "ZS VA", "ZS FR", "ZS SC", "ZS AC", "ZS E2E", "ZS Avg",
        "FS VA", "FS FR", "FS SC", "FS AC", "FS E2E", "FS Avg",
        "Tok/s", "Mem", "GPU-hrs",
    ]
    rows = []
    for domain in sorted(data.keys()):
        dom_data = data[domain]
        for setting in ["Trained", "RL_Verification"]:
            setting_label = "+Trained" if setting == "Trained" else "+RL+Verification"
            sd = dom_data.get(setting, {})
            zs = sd.get("ZS", {})
            fs = sd.get("FS", {})
            row = [
                domain.replace("_", " ").title(), setting_label,
                zs.get("VA",""), zs.get("FR",""), zs.get("SC",""),
                zs.get("AC",""), zs.get("E2E",""), zs.get("Avg",""),
                fs.get("VA",""), fs.get("FR",""), fs.get("SC",""),
                fs.get("AC",""), fs.get("E2E",""), fs.get("Avg",""),
                "", "", "",
            ]
            rows.append(row)
    _print_table(headers, rows, "TABLE 3 — Domain-wise Results (Gemma-2B)")


def print_table4(data: List) -> None:
    headers = [
        "Setting",
        "ZS VA", "ZS FR", "ZS SC", "ZS AC", "ZS E2E", "ZS Avg",
        "FS VA", "FS FR", "FS SC", "FS AC", "FS E2E", "FS Avg",
        "Tok/s", "Mem", "GPU-hrs",
    ]
    rows = []
    for entry in data:
        zs = entry.get("ZS", {})
        fs = entry.get("FS", {})
        row = [
            entry["Setting"],
            zs.get("VA",""), zs.get("FR",""), zs.get("SC",""),
            zs.get("AC",""), zs.get("E2E",""), zs.get("Avg",""),
            fs.get("VA",""), fs.get("FR",""), fs.get("SC",""),
            fs.get("AC",""), fs.get("E2E",""), fs.get("Avg",""),
            entry.get("Tok/s",""), entry.get("Mem",""), entry.get("GPU-hrs",""),
        ]
        rows.append(row)
    _print_table(headers, rows, "TABLE 4 — Ablation Study (Gemma-2B)")

def print_domain_table(model_key: str, table_num: int, data: Dict) -> None:
    headers = [
        "Domain", "Setting",
        "ZS VA", "ZS FR", "ZS SC", "ZS AC", "ZS E2E", "ZS Avg",
        "FS VA", "FS FR", "FS SC", "FS AC", "FS E2E", "FS Avg",
        "Tok/s", "Mem", "GPU-hrs",
    ]
    rows = []
    for domain in sorted(data.keys()):
        dom_data = data[domain]
        for setting in ["Trained", "RL_Verification"]:
            sd = dom_data.get(setting, {})
            zs = sd.get("ZS", {})
            fs = sd.get("FS", {})
            label = "+Trained" if setting == "Trained" else "+RL+Verification"
            row = [
                domain.replace("_", " ").title(), label,
                zs.get("VA",""), zs.get("FR",""), zs.get("SC",""),
                zs.get("AC",""), zs.get("E2E",""), zs.get("Avg",""),
                fs.get("VA",""), fs.get("FR",""), fs.get("SC",""),
                fs.get("AC",""), fs.get("E2E",""), fs.get("Avg",""),
                "", "", "",
            ]
            rows.append(row)
    _print_table(headers, rows, f"TABLE {table_num} — Domain-wise Results ({model_key})")


def print_ablation_table(model_key: str, table_num: int, data: List) -> None:
    headers = [
        "Setting",
        "ZS VA", "ZS FR", "ZS SC", "ZS AC", "ZS E2E", "ZS Avg",
        "FS VA", "FS FR", "FS SC", "FS AC", "FS E2E", "FS Avg",
        "Tok/s", "Mem", "GPU-hrs",
    ]
    rows = []
    for entry in data:
        zs = entry.get("ZS", {})
        fs = entry.get("FS", {})
        row = [
            entry["Setting"],
            zs.get("VA",""), zs.get("FR",""), zs.get("SC",""),
            zs.get("AC",""), zs.get("E2E",""), zs.get("Avg",""),
            fs.get("VA",""), fs.get("FR",""), fs.get("SC",""),
            fs.get("AC",""), fs.get("E2E",""), fs.get("Avg",""),
            entry.get("Tok/s",""), entry.get("Mem",""), entry.get("GPU-hrs",""),
        ]
        rows.append(row)
    _print_table(headers, rows, f"TABLE {table_num} — Ablation Study ({model_key})")


# ── Main entry point ──────────────────────────────────────────────────────────

def print_all_tables(results_file: str) -> None:
    if not os.path.exists(results_file):
        print(f"Error: Could not find results file at {results_file}")
        sys.exit(1)

    with open(results_file) as f:
        raw = json.load(f)
    print(f"\n[Using results from: {results_file}]")
    
    # 1. Map Table 2 data (Main)
    t2_data = {}
    for mk, md in raw.items():
        t2_data[mk] = {"compute": {}}
        for sk in ["Base", "Trained", "RL_Verification"]:
            if sk in md.get("main", {}):
                t2_data[mk][sk] = {
                    "ZS": md["main"][sk].get("ZS", {}).get("metrics", {}),
                    "FS": md["main"][sk].get("FS", {}).get("metrics", {})
                }
                comp = md["main"][sk].get("ZS", {}).get("compute", {})
                t2_data[mk]["compute"]["Tok/s"] = comp.get("Tok/s", "")
                t2_data[mk]["compute"]["Mem"] = comp.get("Mem", "")
                gpu_key = {"Base": "GPU-hrs_base", "Trained": "GPU-hrs_trained", "RL_Verification": "GPU-hrs_rl"}[sk]
                t2_data[mk]["compute"][gpu_key] = comp.get("GPU-hrs", "")
    
    print_table2(data=t2_data)
    
    # 2. Map Table 3 (Gemma domain)
    gemma_dom = raw.get("Gemma-2B", {}).get("domain", {})
    mapped_gemma_dom = {}
    for dom, ddata in gemma_dom.items():
        mapped_gemma_dom[dom] = {}
        for sk in ["Trained", "RL_Verification"]:
            if sk in ddata:
                mapped_gemma_dom[dom][sk] = {
                    "ZS": ddata[sk].get("ZS", {}),
                    "FS": ddata[sk].get("FS", {})
                }
    if mapped_gemma_dom:
        print_table3(data=mapped_gemma_dom)
    
    # 3. Map Table 4 (Gemma ablation)
    gemma_abl = raw.get("Gemma-2B", {}).get("ablation", [])
    mapped_gemma_abl = []
    for abl in gemma_abl:
        mapped_gemma_abl.append({
            "Setting": abl.get("Setting", ""),
            "ZS": abl.get("ZS", {}),
            "FS": abl.get("FS", {}),
            "Tok/s": "",
            "Mem": "",
            "GPU-hrs": "",
        })
    if mapped_gemma_abl:
        print_table4(data=mapped_gemma_abl)
    
    other_models = [k for k in raw.keys() if k != "Gemma-2B"]
    
    # Dynamic Domain Tables (start at 5)
    table_num = 5
    for mk in other_models:
        dom_data = raw.get(mk, {}).get("domain", {})
        mapped_dom = {}
        for dom, ddata in dom_data.items():
            mapped_dom[dom] = {}
            for sk in ["Trained", "RL_Verification"]:
                if sk in ddata:
                    mapped_dom[dom][sk] = {
                        "ZS": ddata[sk].get("ZS", {}),
                        "FS": ddata[sk].get("FS", {})
                    }
        if mapped_dom:
            print_domain_table(mk, table_num=table_num, data=mapped_dom)
            table_num += 1
        
    # Dynamic Ablation Tables
    table_num = 9
    for mk in other_models:
        abl_data = raw.get(mk, {}).get("ablation", [])
        mapped_abl = []
        for abl in abl_data:
            mapped_abl.append({
                "Setting": abl.get("Setting", ""),
                "ZS": abl.get("ZS", {}),
                "FS": abl.get("FS", {}),
                "Tok/s": "",
                "Mem": "",
                "GPU-hrs": "",
            })
        if mapped_abl:
            print_ablation_table(mk, table_num=num, data=mapped_abl)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Tables 2–12")
    parser.add_argument("--results-file", type=str, default="results/raw_results.json",
                        help="Path to raw_results.json from experiments")
    args = parser.parse_args()
    print_all_tables(results_file=args.results_file)
