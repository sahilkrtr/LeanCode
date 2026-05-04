import os

# Project root (relative paths)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "LeanData")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
CHECKPOINTS_DIR = os.path.join(PROJECT_ROOT, "checkpoints")

# ── Models (HuggingFace Hub IDs) ─────────────────────────────────────────────
MODELS = {
    "Phi-2":          "microsoft/phi-2",
    "TinyLlama":      "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "Qwen2-1.5B":     "Qwen/Qwen2-1.5B",
    "Gemma-2B":       "google/gemma-2b",
    "DeepSeek-1.3B":  "deepseek-ai/deepseek-coder-1.3b-instruct",
}

# ── Hyperparameters ────────────────────────────────────────────────────
HYPERPARAMS = {
    "max_trajectory_length": 32,      # T
    "discount_factor":       1.0,     # γ
    "learning_rate":         3e-5,
    "adam_beta1":            0.9,
    "adam_beta2":            0.95,
    "num_epochs":            3,
    "gradient_accumulation": 8,
    "batch_size":            4,
    "effective_batch_size":  32,
    "grad_clip_norm":        1.0,
    "temperature":           0.7,     # τ
    "max_reprompt_attempts": 3,       # K
    "max_new_tokens":        512,
    "seed":                  42,
}


