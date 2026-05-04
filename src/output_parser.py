import re
from typing import Any, Dict, List, Optional, Tuple

_DRAFT_RE   = re.compile(
    r"(?:\[\d*\]\s*|\*\*)?DRAFT\]?\s*[:\-]?\*?\*?\s*(.*?)(?=SKETCH|PROVE|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_SKETCH_RE  = re.compile(
    r"(?:\[\d*\]\s*|\*\*)?SKETCH\]?\s*[:\-]?\*?\*?\s*(.*?)(?=PROVE|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_PROVE_RE   = re.compile(
    r"(?:\[\d*\]\s*|\*\*)?PROVE?\]?\s*[:\-]?\*?\*?\s*(.*?)(?=Formal Verification|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_LEAN_RE    = re.compile(r"Formal Verification[^:]*:(.*?)(?=Verification:|\Z)", re.DOTALL | re.IGNORECASE)
_VERIF_RE   = re.compile(r"Verification:\s*(.*?)(?=Final Answer:|\Z)", re.DOTALL | re.IGNORECASE)
_ANSWER_RE  = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)
_COUNTER_RE = re.compile(r"counterexample[:\s]+(.*?)$", re.DOTALL | re.IGNORECASE)

_HYP_RE     = re.compile(r"H\(x\)\s*=\s*\{([^}]*)\}", re.DOTALL | re.IGNORECASE)
_PHI_RE     = re.compile(r"phi\(x\)[:\s]+(.*?)$", re.MULTILINE | re.IGNORECASE)
_THEOREM_RE = re.compile(r"theorem\s+\w+", re.IGNORECASE)
_IMPORT_RE  = re.compile(r"import\s+Mathlib|import\s+Std", re.IGNORECASE)
_TACTIC_RE  = re.compile(
    r"\b(norm_num|ring|linarith|positivity|simp|exact|apply|constructor|"
    r"intro|rfl|omega|decide|trivial|push_neg|use|have|obtain|cases|induction)\b",
    re.IGNORECASE,
)

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


def parse_output(text: str) -> Dict[str, Any]:

    result: Dict[str, Any] = {
        "draft": "", "sketch": "", "hypotheses": [], "prove": "",
        "formal_spec": "", "lean_code": "", "verification": "",
        "counterexample": "", "final_answer": "",
        "has_draft": False, "has_sketch": False,
        "has_prove": False, "has_lean": False,
        "raw": text,
    }

    m = _DRAFT_RE.search(text)
    if m:
        result["draft"] = m.group(1).strip()
        result["has_draft"] = bool(result["draft"])

    m = _SKETCH_RE.search(text)
    if m:
        result["sketch"] = m.group(1).strip()
        result["has_sketch"] = bool(result["sketch"])
        result["hypotheses"] = _parse_hypotheses(result["sketch"])

    m = _PROVE_RE.search(text)
    if m:
        result["prove"] = m.group(1).strip()
        result["has_prove"] = bool(result["prove"])
        pm = _PHI_RE.search(result["prove"])
        if pm:
            result["formal_spec"] = pm.group(1).strip()

    m = _LEAN_RE.search(text)
    if m:
        result["lean_code"] = m.group(1).strip()
        result["has_lean"] = bool(result["lean_code"])

    m = _VERIF_RE.search(text)
    if m:
        v = m.group(1).strip()
        result["verification"] = v
        cm = _COUNTER_RE.search(v)
        if cm:
            result["counterexample"] = cm.group(1).strip()

    m = _ANSWER_RE.search(text)
    if m:
        result["final_answer"] = m.group(1).strip()

    return result


def _parse_hypotheses(sketch: str) -> List[str]:
    m = _HYP_RE.search(sketch)
    if m:
        inner = m.group(1)
    else:
        inner = sketch
    hyps = [h.strip() for h in re.split(r"[,\n]", inner) if h.strip()]
    return hyps


_SECTION_RE = re.compile(
    r"\[(?:[A-Z0-9_\s]+)\]",  # any [UPPERCASE] label in the output
    re.IGNORECASE,
)

def check_structural_consistency(parsed: Dict[str, Any]) -> bool:
    has_draft  = parsed["has_draft"]
    has_sketch = parsed["has_sketch"]
    has_prove  = parsed["has_prove"]
    has_lean   = bool(parsed["lean_code"])
    has_answer = bool(parsed["final_answer"].strip())

    lean = parsed["lean_code"]
    lean_ok = bool(
        has_lean and (
            _THEOREM_RE.search(lean) or _IMPORT_RE.search(lean) or _TACTIC_RE.search(lean)
        )
    )

    if has_draft and has_sketch and has_prove:
        return True

    if sum([has_draft, has_sketch, has_prove]) >= 2 and lean_ok:
        return True

    raw = parsed.get("raw", "")
    bracket_sections = _SECTION_RE.findall(raw)
    if len(bracket_sections) >= 3 and (lean_ok or has_answer):
        return True

    if lean_ok and has_answer:
        return True

    return False


def check_alignment_consistency(
    parsed: Dict[str, Any],
    ground_truth: Optional[Dict] = None,
) -> bool:

    hyps = parsed["hypotheses"]
    draft = parsed["draft"].lower()
    prove = (parsed["prove"] + " " + parsed["lean_code"]).lower()

    if ground_truth is not None:
        gt_hyps: List[str] = ground_truth.get("hypotheses", [])
        gt_steps: List[str] = ground_truth.get("reasoning_steps", [])
        gt_text = " ".join(str(h) for h in gt_hyps + gt_steps).lower()

        # Extract all meaningful tokens from model's draft+sketch
        model_text = (draft + " " + " ".join(hyps)).lower()
        gt_tokens = set(re.findall(r"[a-zA-Z_]\w*", gt_text))
        gt_tokens = {t for t in gt_tokens if len(t) > 2}  # skip short tokens
        if gt_tokens:
            overlap = sum(1 for t in gt_tokens if t in model_text)
            if overlap / len(gt_tokens) >= 0.3:
                return True

    if not hyps:
        return parsed["has_draft"] and parsed["has_prove"]

    var_names: List[str] = []
    for h in hyps:
        tokens = re.findall(r"[a-zA-Z_]\w*", h)
        var_names.extend(t.lower() for t in tokens if len(t) > 1)

    if not var_names:
        return True

    aligned = sum(1 for v in var_names if v in draft or v in prove)
    return aligned >= len(var_names) * 0.5


# ── Verification Accuracy (VA) ────────────────────────────────────────────────

def check_verification(
    parsed: Dict[str, Any],
    ground_truth: Optional[Dict] = None,
) -> bool:

    verif = parsed.get("verification", "").lower()
    if "symbolically_verified" in verif or "verified" in verif:
        if "counterexample" not in verif and "failed" not in verif:
            if _has_plausible_lean(parsed["lean_code"]):
                if ground_truth is not None:
                    return _numeric_match(
                        parsed["final_answer"],
                        ground_truth.get("final_answer", ""),
                    )
                return True

    if ground_truth is not None:
        return _numeric_match(
            parsed["final_answer"],
            ground_truth.get("final_answer", ""),
        )
    return False


def _has_plausible_lean(lean_code: str) -> bool:
    """Quick heuristic: code has imports AND a theorem AND at least one tactic."""
    if not lean_code:
        return False
    return bool(
        (_IMPORT_RE.search(lean_code) or "theorem" in lean_code.lower())
        and _TACTIC_RE.search(lean_code)
    )


def _numeric_match(pred: str, gt: str, tol: float = 0.05) -> bool:
    """Check if the numeric value in *pred* is within *tol* relative error of *gt*."""
    if not pred or not gt:
        return False
    pred_nums = _NUM_RE.findall(str(pred).replace(",", ""))
    gt_nums   = _NUM_RE.findall(str(gt).replace(",", ""))
    if not pred_nums or not gt_nums:
        # Fall back to string similarity
        return str(pred).strip().lower() == str(gt).strip().lower()
    try:
        pv, gv = float(pred_nums[-1]), float(gt_nums[-1])
        if gv == 0:
            return abs(pv) < 1e-6
        return abs(pv - gv) / abs(gv) <= tol
    except ValueError:
        return False


def check_falsification(
    parsed: Dict[str, Any],
    ground_truth: Optional[Dict] = None,
) -> bool:

    cex = parsed.get("counterexample", "").strip()
    verif = parsed.get("verification", "").lower()

    has_cex = bool(cex) or "counterexample" in verif
    if not has_cex:
        return False

    if not _NUM_RE.findall(cex or verif):
        return "modified" in (cex + verif).lower() or bool(cex)

    if ground_truth is not None:
        gt_ans = str(ground_truth.get("final_answer", ""))
        return not _numeric_match(cex, gt_ans, tol=0.001)

    return True


def check_e2e(va: bool, fr: bool) -> bool:
    """E2E = successful verification OR valid falsification."""
    return va or fr


def evaluate_output(
    raw_output: str,
    ground_truth: Optional[Dict] = None,
    require_structural: bool = True,
) -> Dict[str, bool]:

    parsed = parse_output(raw_output)
    sc = check_structural_consistency(parsed)
    ac = check_alignment_consistency(parsed, ground_truth) if sc else False
    va = check_verification(parsed, ground_truth) if sc else False
    fr = check_falsification(parsed, ground_truth)
    e2e = check_e2e(va, fr)
    return {"sc": sc, "ac": ac, "va": va, "fr": fr, "e2e": e2e, "parsed": parsed}
