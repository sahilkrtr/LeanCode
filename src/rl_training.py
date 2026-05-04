import os
import json
import logging
from typing import Dict, List, Optional, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import HYPERPARAMS, CHECKPOINTS_DIR

logger = logging.getLogger(__name__)

def _compute_returns(rewards: List[float], gamma: float) -> List[float]:
    G = 0.0
    returns = []
    for r in reversed(rewards):
        G = r + gamma * G
        returns.insert(0, G)
    if not returns: return []
    mean = sum(returns) / len(returns)
    std = (sum((x - mean) ** 2 for x in returns) / len(returns)) ** 0.5
    return [(g - mean) / (std + 1e-8) for g in returns]

class RLTrainer:
    def __init__(
        self,
        model_key: str,
        hf_token: Optional[str] = None,
        checkpoint_dir: str = CHECKPOINTS_DIR,
    ):
        from src.model_inference import HFInferenceModel
        from src.lean_verifier import LeanEnvironment
        self.model_key = model_key
        self.checkpoint_dir = checkpoint_dir
        self._model = HFInferenceModel(model_key, hf_token=hf_token)
        self._env = LeanEnvironment()

    def train(
        self,
        train_items: List[Dict],
        num_epochs: int = HYPERPARAMS["num_epochs"],
        temperature: float = HYPERPARAMS["temperature"],
        max_traj_len: int = HYPERPARAMS["max_trajectory_length"],
    ) -> Dict:
        import torch
        from src.prompts import build_tactic_prompt

        self._model._load()
        self._model._model.train()

        optimizer = torch.optim.Adam(
            self._model._model.parameters(),
            lr=HYPERPARAMS["learning_rate"],
            betas=(HYPERPARAMS["adam_beta1"], HYPERPARAMS["adam_beta2"]),
        )
        gamma = HYPERPARAMS["discount_factor"]
        grad_accum = HYPERPARAMS["gradient_accumulation"]
        total_episodes = 0
        total_reward_accum = 0.0
        epoch_reward_history = []

        for epoch in range(num_epochs):
            epoch_reward = 0.0
            optimizer.zero_grad()

            for batch_idx, item in enumerate(train_items):
                proof_state = self._env.reset(item)
                log_probs_t = []
                rewards_t = []

                for step in range(max_traj_len):
                    if proof_state.complete: break
                    
                    tactic_prompt = build_tactic_prompt(
                        proof_state.state_text,
                        item.get("lean_domain", "physics"),
                        temperature,
                    )
                    # Sample tactic and get differentiable log-prob in one go
                    tactic, lp_tensor, _ = self._model.generate_with_logprob(tactic_prompt)
                    
                    # Execute in Lean
                    _, _, complete, reward = proof_state.apply_tactic(tactic.strip())
                    
                    log_probs_t.append(lp_tensor)
                    rewards_t.append(reward)
                    if complete: break

                if log_probs_t and rewards_t:
                    returns = _compute_returns(rewards_t, gamma)
                    loss = -sum(lp * r for lp, r in zip(log_probs_t, returns))
                    (loss / grad_accum).backward()

                    if (batch_idx + 1) % grad_accum == 0:
                        torch.nn.utils.clip_grad_norm_(self._model._model.parameters(), HYPERPARAMS["grad_clip_norm"])
                        optimizer.step()
                        optimizer.zero_grad()

                episode_reward = sum(rewards_t)
                epoch_reward += episode_reward
                total_episodes += 1
                total_reward_accum += episode_reward

            avg = epoch_reward / max(len(train_items), 1)
            epoch_reward_history.append(avg)
            logger.info(f"Epoch {epoch+1}/{num_epochs}: avg_reward={avg:.4f}")

        self._save_checkpoint(optimizer, epoch_reward_history)
        return {
            "model_key": self.model_key,
            "num_epochs": num_epochs,
            "average_reward": total_reward_accum / max(total_episodes, 1),
            "epoch_rewards": epoch_reward_history,
        }

    def _save_checkpoint(self, optimizer, epoch_rewards: List[float]) -> None:
        import torch
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        weights_path = os.path.join(self.checkpoint_dir, f"{self.model_key}_rl_weights.pt")
        meta_path = os.path.join(self.checkpoint_dir, f"{self.model_key}_rl.json")
        torch.save({"model_state_dict": self._model._model.state_dict(), "optimizer_state_dict": optimizer.state_dict()}, weights_path)
        with open(meta_path, "w") as f:
            json.dump({"model_key": self.model_key, "checkpoint": weights_path, "final_reward": epoch_rewards[-1] if epoch_rewards else 0.0}, f, indent=2)
        logger.info(f"RL checkpoint saved: {weights_path}")
