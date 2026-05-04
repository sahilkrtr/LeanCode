import re
import subprocess
import shutil
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

_LEAN_BIN = shutil.which("lean") or shutil.which("lake")

# ─────────────────────────────────────────────
# LEAN EXECUTION
# ─────────────────────────────────────────────

def verify_lean_proof(lean_code: str, timeout: int = 15) -> Tuple[bool, str]:
    if _LEAN_BIN is None:
        return False, "Lean 4 not found"
    return _verify_with_lean4(lean_code, timeout)

def _verify_with_lean4(lean_code: str, timeout: int) -> Tuple[bool, str]:
    import tempfile, os
    try:
        with tempfile.NamedTemporaryFile(suffix=".lean", mode="w", delete=False) as f:
            f.write(lean_code)
            fname = f.name
        result = subprocess.run(
            [_LEAN_BIN, fname],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        os.unlink(fname)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def dataset_verification_check(item: Dict) -> bool:
    vr = item.get("verification_result", "")
    if isinstance(vr, bool): return vr
    vr_str = str(vr).lower()
    return "verified" in vr_str and "failed" not in vr_str

def verify_counterexample(cex: str, gt_ans: str, hyps: list) -> bool:
    if not cex: return False
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", cex)
    gt_nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", str(gt_ans))
    if nums and gt_nums:
        try:
            pv, gv = float(nums[-1]), float(gt_nums[-1])
            if abs(pv - gv) > (0.001 * abs(gv) if gv != 0 else 0.001): return True
        except: pass
    return any(v.lower() in cex.lower() for h in hyps for v in re.findall(r"[a-zA-Z_]\w*", str(h)) if len(v) > 1)


def extract_goal_count(feedback: str) -> int:
    m = re.search(r"(\d+)\s+goals?", feedback.lower())
    if m: return int(m.group(1))
    if "no goals" in feedback.lower(): return 0
    return 1 if feedback.strip() else 0

def extract_goal_text(feedback: str) -> str:
    if not feedback.strip(): return "no goals"
    return feedback.strip()[:300]


class LeanProofState:
    def __init__(self, lean_code: str, item: Dict, env: "LeanEnvironment"):
        self.lean_code = lean_code
        self.item = item
        self.env = env
        self.tactics: List[str] = []
        self.complete = False
        self.goal_count = 1
        self.goal_text = ""
        self._init_state()

    def _init_state(self):
        success, feedback = verify_lean_proof(self.lean_code)
        self.goal_count = extract_goal_count(feedback)
        self.goal_text = extract_goal_text(feedback)
        self.complete = success

    @property
    def state_text(self) -> str:
        recent = "\n".join(f"  {t}" for t in self.tactics[-3:]) if self.tactics else "  (none)"
        return (
            f"Current Goals: {self.goal_count}\n"
            f"{self.goal_text}\n\n"
            f"Recent tactics:\n{recent}"
        )

    def apply_tactic(self, tactic: str) -> Tuple[bool, bool, bool, float]:
        success, new_code, reward, new_goals, new_text = self.env.run_tactic(
            self.lean_code, tactic, self.goal_count
        )
        if success:
            self.lean_code = new_code
            self.tactics.append(tactic)
            self.goal_count = new_goals
            self.goal_text = new_text
        self.complete = (self.goal_count == 0)
        return success, success, self.complete, reward

class LeanEnvironment:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        if _LEAN_BIN is None: raise RuntimeError("Lean 4 not found")

    def reset(self, item: Dict) -> LeanProofState:
        code = item.get("lean_proof_script", item.get("lean_formal_statement", ""))
        return LeanProofState(code, item, self)

    def run_tactic(self, lean_code: str, tactic: str, prev_goal_count: int):
        extended_code = lean_code.rstrip() + f"\n  {tactic}"
        success, feedback = _verify_with_lean4(extended_code, self.timeout)
        new_goal_count = extract_goal_count(feedback)
        new_goal_text = extract_goal_text(feedback)

        if success:
            reward = 1.0
        else:
            if new_goal_count == 0 and "error" not in feedback.lower():
                reward = 1.0
            elif new_goal_count < prev_goal_count:
                reward = 0.5
            elif "error" in feedback.lower():
                reward = -1.0
            else:
                reward = 0.0

        return (
            success,
            extended_code if success else lean_code,
            reward,
            new_goal_count,
            new_goal_text,
        )