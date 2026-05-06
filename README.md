# LeanData: Verification-Augmented Scientific Reasoning for Small Language Models

Official implementation for:

> **Does Small Language Models Achieve Scientific Reasoning via Verification-Augmented Reasoning?**

This repository provides the full implementation of **LeanData**, a benchmark and training framework for evaluating scientific reasoning in Small Language Models (SLMs) using:

- formal Lean4 verification
- counterexample generation
- reinforcement learning with symbolic feedback
- premise-grounded scientific reasoning
- verification-augmented optimization

The framework studies whether verification signals from a proof assistant can compensate for limited model capacity in 1B–3B parameter SLMs.

---

# Overview

Scientific reasoning requires more than producing correct final answers. Models must generate:

- logically consistent intermediate reasoning
- valid assumptions
- executable symbolic specifications
- formally verifiable derivations
- falsifiable scientific hypotheses

LeanData evaluates these properties through a closed neuro-symbolic loop using Lean4.

Given a scientific problem `x`, the framework constructs:

```text
(r, H(x), φ(x))
```

where:

- `r` = structured reasoning steps
- `H(x)` = assumptions/equations/constraints
- `φ(x)` = executable Lean specification

The specification is then:

- formally verified in Lean4
- falsified through counterexample generation
- optimized using RL with proof feedback

---

# Repository Structure

```text
.
├── experiments/                 # Experiment scripts/configurations
├── results/                     # Saved outputs and generated tables
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py           # Dataset loading and preprocessing
│   ├── evaluator.py             # Evaluation pipeline
│   ├── lean_verifier.py         # Lean4 proof execution
│   ├── metrics.py               # Benchmark metrics
│   ├── model_inference.py       # Model generation/inference
│   ├── output_parser.py         # Parsing structured outputs
│   ├── prompts.py               # Prompt templates
│   └── rl_training.py           # PPO-based RL training
│
├── run_experiments.py           # Full experiment runner
├── generate_tables.py           # Table generation for paper
├── config.py                    # Global configuration
├── main.py                      # Main execution script
├── requirements.txt
└── .gitignore
```

---

# LeanData Dataset

LeanData extends scientific reasoning benchmarks into formal verification settings.

The dataset contains:

- natural-language scientific problems
- structured reasoning traces
- symbolic assumptions/equations
- Lean4 formal specifications
- verified proofs
- executable counterexamples

---

# Scientific Domains

LeanData spans 10 scientific domains:

| Domain | Examples |
|---|---|
| Physics | Thermodynamics, mechanics |
| Chemistry | Stoichiometry, gas laws |
| Probability | Conditional probability |
| Calculus | Derivatives, integrals |
| Differential Equations | ODE reasoning |
| Statistics | Variance, distributions |
| Thermodynamics | State transformations |
| Quantum Mechanics | Wave/energy equations |
| Geometry | Formal geometric proofs |
| Linear Algebra | Matrix/vector relations |

---

# Verification Pipeline

The framework follows a Draft–Sketch–Prove reasoning pipeline.

## Stage 1 — Draft

Generate structured reasoning steps:

```text
r = (r1, r2, ..., rk)
```

## Stage 2 — Sketch

Extract assumptions/equations:

```text
H(x) = {h1, h2, ..., hm}
```

including:

- equations
- variable constraints
- unit consistency
- dimensional assumptions

## Stage 3 — Prove

Generate executable Lean specifications:

```text
φ(x)
```

which are formally executed inside Lean4.

---

# Verification Types

The framework supports multiple verification levels:

| Verification Type | Description |
|---|---|
| Numeric Verification | Final-value checking |
| Equation Verification | Equation reconstruction |
| Dimensional Verification | Unit consistency |
| Symbolic Verification | Algebraic transformations |
| Premise-Grounded Verification | Joint reasoning/assumption/specification consistency |

---

# Counterexample Generation

LeanData supports falsification-based reasoning.

Counterexamples are generated through:

- equation perturbation
- state-variable modification
- unit/dimensional violations
- assumption contradiction
- symbolic inconsistency

A candidate counterexample `x'` is accepted only if:

```text
¬φ(x')
```

holds under formal execution.

---

# Reinforcement Learning Framework

The repository implements verification-augmented RL using PPO.

Training includes:

- PPO policy optimization
- online trajectory rollouts
- Generalized Advantage Estimation (GAE)
- KL-regularized updates
- value-function learning
- proof-state feedback

The model learns policies:

```text
πθ(at | st)
```

over Lean proof states and tactics.

---

# Supported Models

The benchmark currently supports:

| Model | Parameters |
|---|---|
| Phi-2 | 2.7B |
| TinyLlama | 1.1B |
| Qwen2-1.5B | 1.5B |
| Gemma-2B | 2B |
| DeepSeek-1.3B | 1.3B |

---

# Evaluation Metrics

The benchmark evaluates five reasoning dimensions.

| Metric | Description |
|---|---|
| VA | Verification Accuracy |
| FR | Falsification Rate |
| SC | Structural Consistency |
| AC | Alignment Consistency |
| E2E | End-to-End Success |

---
