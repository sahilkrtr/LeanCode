import os
import time
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MODELS, HYPERPARAMS

HF_TOKEN = os.environ.get("HF_TOKEN", "")

_API_MODELS = set()
_API_COMPLETIONS = "https://router.huggingface.co/featherless-ai/v1/completions"

_CHAT_MODELS = {"TinyLlama", "Qwen2-1.5B", "DeepSeek-1.3B"}


def _device():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except:
        pass
    return "cpu"


class HFInferenceModel:

    def __init__(self, model_key: str, hf_token: Optional[str] = None):
        self.model_key = model_key
        self.model_id = MODELS[model_key]
        self.temperature = HYPERPARAMS["temperature"]
        self.max_new_tokens = HYPERPARAMS["max_new_tokens"]
        self.hf_token = hf_token or HF_TOKEN

        self._use_api = model_key in _API_MODELS
        self._use_chat = model_key in _CHAT_MODELS

        self._tokenizer = None
        self._model = None
        self._loaded = False

    def _load(self):
        if self._loaded or self._use_api:
            return
        self._loaded = True

        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        dev = _device()

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token_id = self._tokenizer.eos_token_id

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=torch.float16 if dev == "cuda" else torch.float32,
        ).to(dev)

        self._model.eval()

    def generate(self, prompt: str) -> Tuple[str, float]:
        self._load()
        start = time.time()

        if self._use_api:
            return "", 0.0

        import torch

        inputs = self._tokenizer(prompt, return_tensors="pt").to(
            next(self._model.parameters()).device
        )

        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=True,
                pad_token_id=self._tokenizer.pad_token_id,
            )

        new_tokens = out[0][inputs["input_ids"].shape[-1]:]

        text = self._tokenizer.decode(new_tokens, skip_special_tokens=True)

        return text.strip(), time.time() - start

    def generate_with_logprob(self, prompt: str):
        """
        Correct RL pattern:
        1. Sample with no_grad (fast)
        2. Compute log-prob with grad (single forward pass)
        """
        self._load()

        if self._use_api:
            import torch
            return "", torch.tensor(0.0, requires_grad=True), 0.0

        import torch
        import torch.nn.functional as F

        start = time.time()
        device = next(self._model.parameters()).device

        inputs = self._tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=True,
                return_dict_in_generate=True,
                output_scores=False,
                pad_token_id=self._tokenizer.pad_token_id,
            )

        # strip prompt
        full_ids = out.sequences
        gen_ids = full_ids[:, inputs["input_ids"].shape[-1]:]

        text = self._tokenizer.decode(gen_ids[0], skip_special_tokens=True)

        full_input = torch.cat([inputs["input_ids"], gen_ids], dim=1)

        outputs = self._model(full_input)
        logits = outputs.logits

        shift_logits = logits[:, :-1, :]
        shift_labels = full_input[:, 1:]

        log_probs = F.log_softmax(shift_logits, dim=-1)

        token_log_probs = log_probs.gather(
            2, shift_labels.unsqueeze(-1)
        ).squeeze(-1)

        start_idx = inputs["input_ids"].shape[-1] - 1
        completion_log_probs = token_log_probs[:, start_idx:]

        total_log_prob = completion_log_probs.sum()

        return text.strip(), total_log_prob, time.time() - start

    def load_checkpoint(self, path: str):
        self._load()

        if self._use_api:
            return

        import torch

        ckpt = torch.load(path, map_location=next(self._model.parameters()).device)

        if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
            self._model.load_state_dict(ckpt["model_state_dict"])
        else:
            self._model.load_state_dict(ckpt)

    def save_checkpoint(self, path: str):
        if self._use_api:
            return
        import torch
        torch.save(self._model.state_dict(), path)


class ModelPool:

    def __init__(self, model_keys=None):
        keys = model_keys or list(MODELS.keys())
        self.models = {k: HFInferenceModel(k) for k in keys}

    def get(self, model_key: str):
        return self.models[model_key]