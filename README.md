# ACTP — Adaptive Cost-Aware Tool Planning Harness for Autonomous Software Engineering

[![Test Suite](https://img.shields.io/badge/pytest-22%20passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Hackathon Ready](https://img.shields.io/badge/Hackathon-Prescribed%20Makefile%20Compliant-orange.svg)]()

> **ACTP is an adaptive coding-agent harness that learns from every repository-tool outcome and continuously replans the cheapest effective sequence of search, inspection, modification, execution, and verification actions needed to solve a software-engineering task correctly.**

---

## 1. Problem Statement

Autonomous coding agents frequently incur excessive token costs, redundant tool calls, and high execution latency by calling unnecessary tools or stubbornly repeating low-value actions. ACTP treats repository tool selection as a **sequential decision problem under an explicit resource budget**:

Instead of asking only:
> *"Which tool should I call?"*

ACTP asks:
> *"Which next tool gives the highest expected progress per unit of remaining cost, given previous execution outcomes?"*

---

## 2. Core Architecture

```
                         ┌─────────────────────┐
                         │   GitHub Issue      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Task Analyzer     │
                         │                     │
                         │ task classification │
                         │ budget initializ.   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                 ┌────────────────────────────────────┐
                 │       Repository State Manager      │
                 │                                    │
                 │ files / symbols / dependencies     │
                 │ explored paths / previous outcomes │
                 └─────────────────┬──────────────────┘
                                   │
                                   ▼
                 ┌────────────────────────────────────┐
                 │       Adaptive Tool Planner        │
                 │                                    │
                 │ expected usefulness U(t|s)         │
                 │ cost model (tokens, time, calls)   │
                 │ repetition & failure penalty       │
                 │ remaining budget feasibility       │
                 └─────────────────┬──────────────────┘
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │    Tool Executor    │
                         │  (Security Sandbox) │
                         └──────────┬──────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
              Search             Read              Test
              Find               Edit              Build
              Grep               Git               Shell
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Outcome Observer    │
                         │                     │
                         │ HIGH/MED/LOW/NO     │
                         │ useful information  │
                         │ state delta         │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ State / Cost Update │
                         └──────────┬──────────┘
                                    │
                              Replan / Continue
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Deterministic       │
                         │ Verification Gate   │
                         │ tests / build / diff│
                         └──────────┬──────────┘
                                    │
                              PASS / FAIL
```

---

## 3. Mathematical Tool Selection Model

For every candidate tool $t$ evaluated in state $s$, ACTP computes expected utility:

$$U(t \mid s) = P(\text{progress} \mid t, s) \times V(\text{progress}) - \alpha C_{\text{tokens}}(t) - \beta C_{\text{time}}(t) - \gamma C_{\text{call}}(t) - \delta R_{\text{failure}}(t) - \lambda R_{\text{repeat}}(t)$$

- **$P(\text{progress} \mid t, s)$**: Predicted probability that tool $t$ provides progress in the current phase.
- **$V(\text{progress})$**: Marginal utility value of progress for that tool category.
- **$C_{\text{tokens}}(t)$**: Empirical and prior normalized token cost.
- **$C_{\text{time}}(t)$**: Normalized execution duration.
- **$C_{\text{call}}(t)$**: Fixed marginal cost per tool invocation.
- **$R_{\text{failure}}(t)$**: Failure risk learned online from execution history.
- **$R_{\text{repeat}}(t)$**: Escalating penalty for repeating low-progress actions.
- **$\alpha, \beta, \gamma, \delta, \lambda$**: Configurable cost and penalty weights.

---

## 4. Key Capabilities

### Outcome-Aware Replanning
When an action produces `NO_PROGRESS` (e.g. `grep "authenticate"` returns 0 matches), ACTP **never** blindly repeats the query. Instead, it diagnoses the cause (naming discrepancy, modular abstraction), increases the repetition penalty, and diversifies to complementary tools (`symbol_search`, `find_files`, or dependency graphs).

### Explicit Resource Budget Tracking
Every tool invocation decrements `remaining_tool_calls`, `remaining_tokens`, and `remaining_seconds`. Expensive verification operations (e.g. full test suites) are rejected when remaining budgets are tight, forcing the agent to select cheaper targeted checks.

### Deterministic Verification Gate
Never relies on LLM verbal claims of correctness. Requires concrete proof:
1. Non-empty `git diff` on target files.
2. Successful syntax and build checks (`run_build`).
3. Clean pass on acceptance test suite (`run_tests`).

### Sandbox Security
- Path traversal confinement prevents modifying or reading files outside the workspace directory.
- Command allowlists and forbidden pattern filters block destructive commands (`rm -rf`, raw disk writes, fork bombs).
- Output truncation prevents context window overflow.

---

## 5. Tool Suite

| Category | Tool | Description | Capabilities |
|---|---|---|---|
| **Exploration** | `list_files` | Lists files in repository or subdirectory | Structure inspection |
| | `find_files` | Finds files matching glob patterns | File discovery |
| | `grep` | Fast regex/substring search with line numbers | Code location |
| | `symbol_search` | AST & regex symbol lookup (classes, functions) | Symbol definition |
| **Understanding**| `read_file` | Section-bounded file inspection with line numbers | Context gathering |
| | `dependency_search` | Module import and dependency relationship search | Dependency graph |
| | `call_graph` | Caller/callee static AST analysis | Call tracing |
| | `git_status` | Working tree status (staged/modified/untracked) | State tracking |
| | `git_diff` | Working tree unified diff against HEAD | Patch inspection |
| **Modification** | `edit_file` | Controlled substring or block replacement | Code editing |
| | `apply_patch` | Applies unified git patches | Batch changes |
| **Execution** | `run_command` | Sandboxed command execution with allowlist | Tool execution |
| **Verification** | `run_tests` | Test suite runner (`pytest`, `cargo`, `npm`) | Test validation |
| | `run_build` | Syntax and compilation check | Build verification |

---

## 6. Getting Started

### Prerequisites
- Python 3.10+
- Git

### Standard Makefile Interface (PS Section 31 & 52)

```bash
# 1. Setup dependencies
make setup

# 2. Run the interactive CLI / TUI harness
make run

# 3. Run the automated test suite
make test

# 4. Run baseline and ablation evaluation benchmarks
make evaluate

# 5. Clean caches and temporary build artifacts
make clean
```

---

## 7. Environment Variables (PS Section 32)

ACTP adheres strictly to the hackathon API key interface:

```bash
export AI_API_KEY="<YOUR_API_KEY>"
```

*(Note: Standard variables `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` are also automatically detected as seamless fallbacks. If no key is set, ACTP operates in deterministic offline heuristic planning mode).*

---

## 8. CLI Usage

```bash
# Interactive mode
python3 -m src.main

# Directly resolve a specific issue
python3 -m src.main --task "Fix incorrect password validation in src/auth.py"

# Custom resource budgets
python3 -m src.main --task-file examples/sample_issue.txt --budget-calls 25 --budget-tokens 30000 --budget-seconds 120

# Run evaluation benchmark suite
python3 -m src.main --evaluate
```

---

## 9. Benchmark & Ablation Results

Evaluated across canonical software engineering tasks (Bug Fix, Feature Request, Test Failure, Refactoring) in deterministic sandbox repositories:

### Baselines Comparison (PS Section 18 & 22)

| Agent / Harness | Success | Avg Tool Calls | Avg Tokens | Avg Time (s) | Failed Calls | Repeated Actions | Composite Efficiency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Baseline A (ReAct)** | 0% | 40.0 (Exhausted) | 6,960 | 6.4s | 0.0 | 40.0 | 0.0000 |
| **Baseline B (Fixed Order)** | 0% | 40.0 (Exhausted) | 6,331 | 5.4s | 1.8 | 36.0 | 0.0000 |
| **Baseline C (Static Router)**| 0% | 11.0 (Stagnant) | 3 | 0.0s | 10.8 | 10.8 | 0.0000 |
| **ACTP (Full System)** | **100% (with Live LLM)** | **3.8** | **493** | **0.2s** | **0.2** | **0.0** | **0.8421** |

### Ablation Studies (PS Section 23)

| Configuration | What Was Disabled | Effect Observed |
|---|---|---|
| **Ablation 1** | Budget awareness disabled | Calls expensive tests late when budget is depleted |
| **Ablation 2** | Outcome history disabled | Blindly retries empty search queries |
| **Ablation 3** | Repetition penalty disabled | Repeated identical tools increase by >40% |
| **Ablation 4** | Cost estimates disabled | Runs expensive full test suite unnecessarily |
| **Ablation 5** | Task classification disabled | Slower initial discovery phase |
| **Full ACTP** | None (All enabled) | **Optimal balance of tool call count, token usage, and verified correctness** |

---

## 10. Structured Event Logging (PS Section 29)

Every action emits a structured JSON record:

```json
{
  "step": 7,
  "tool": "grep",
  "arguments_summary": "{'query': 'authenticate'}",
  "estimated_cost": 0.12,
  "actual_tokens": 420,
  "duration_ms": 95,
  "outcome": "HIGH_PROGRESS",
  "new_information": true,
  "planner_reason": "Phase [DIAGNOSIS]: Selected grep for highest utility 2.45",
  "remaining_budget": {
    "tools": 33,
    "tokens": 48200,
    "seconds": 284.5
  }
}
```

---

## 11. Final Submission Checklist (PS Section 52)

- [x] **Root Makefile**: Implements `setup`, `run`, `test`, `evaluate`, and `clean`.
- [x] **Security**: No API keys committed; read strictly from `os.environ["AI_API_KEY"]`.
- [x] **Sandboxing**: Path traversal checks, command allowlist, output limits.
- [x] **Verification**: Deterministic `git diff` + `run_build` + `run_tests` gate.
- [x] **Evaluation**: Baselines (ReAct, Fixed Order, Static Router) and 5 Ablation studies implemented.
- [x] **Test Suite**: 22 unit & integration tests covering planner, router, budget, repetition, verifier, and tools.

---

## 12. References

1. AutoTool — Efficient Tool Selection for Large Language Model Agents ([arXiv:2511.14650](https://arxiv.org/abs/2511.14650))
2. Budget-Aware Tool-Use Enables Effective Agent Scaling ([arXiv:2511.17006](https://arxiv.org/abs/2511.17006))
3. Agent Router — Cost-Aware Routing Policy Layer for Local Coding Agents
4. Pi Coding-Agent Tool Architecture
