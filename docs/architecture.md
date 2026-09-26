# ACTP Architecture Documentation

## 1. System Overview

**Adaptive Cost-Aware Tool Planning Harness (ACTP)** is an autonomous coding-agent execution harness that dynamically plans, selects, and replans repository development tools. Rather than replacing the foundation model, ACTP controls the execution layer, resource allocation, and verification.

```
                         ┌─────────────────────┐
                         │   GitHub Issue      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Task Analyzer     │
                         │                     │
                         │ task type           │
                         │ constraints         │
                         │ acceptance clues    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                 ┌────────────────────────────────────┐
                 │       Repository State Manager      │
                 │                                    │
                 │ files / symbols / dependencies     │
                 │ explored paths / previous results  │
                 └─────────────────┬──────────────────┘
                                   │
                                   ▼
                 ┌────────────────────────────────────┐
                 │       Adaptive Tool Planner        │
                 │                                    │
                 │ capability                         │
                 │ expected usefulness                │
                 │ cost model (tokens, time, calls)   │
                 │ failure & repetition history       │
                 │ remaining resource budget          │
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
                         │ success / failure   │
                         │ useful progress     │
                         │ state delta         │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ State / Cost Update │
                         └──────────┬──────────┘
                                    │
                                    ▼
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

## 2. Mathematical Utility Model

Tool selection is treated as a sequential decision problem under explicit constraints. For every candidate tool $t$ evaluated in state $s$:

$$U(t \mid s) = P(\text{progress} \mid t, s) \times V(\text{progress}) - \alpha C_{\text{tokens}}(t) - \beta C_{\text{time}}(t) - \gamma C_{\text{call}}(t) - \delta R_{\text{failure}}(t) - \lambda R_{\text{repeat}}(t)$$

Where:
- $P(\text{progress} \mid t, s)$: Predicted probability of making productive progress.
- $V(\text{progress})$: Utility weight associated with that progress.
- $C_{\text{tokens}}(t)$: Normalized token cost.
- $C_{\text{time}}(t)$: Normalized execution time.
- $C_{\text{call}}(t)$: Fixed marginal cost per invocation.
- $R_{\text{failure}}(t)$: Empirical and prior failure risk.
- $R_{\text{repeat}}(t)$: Escalating penalty for repeating low-progress actions.
- $\alpha, \beta, \gamma, \delta, \lambda$: Configurable cost weights.

---

## 3. Core Subsystems

### Task Analyzer
Classifies incoming issues into canonical software engineering categories:
- `BUG_FIX`
- `FEATURE_REQUEST`
- `TEST_FAILURE`
- `REFACTORING`
- `GENERAL`

### Repository State Manager & Budget Tracker
Tracks:
- Explored files, discovered symbols, modified files
- Remaining tool calls, remaining tokens, remaining seconds
- Failure history and consecutive action counts

### Outcome-Aware Replanner
When an action produces `NO_PROGRESS`, `FAILURE`, or `BLOCKED`:
1. Diagnoses the underlying cause (e.g. empty search, missing file, syntax error).
2. Applies a repetition penalty to prevent repeating the failed action.
3. Diversifies tool selection toward alternative exploration or inspection channels.

### Security Manager
- Workspace confinement: prevents directory traversal attacks outside the workspace directory.
- Command allowlist & forbidden pattern blocking: prevents destructive commands (`rm -rf`, raw disk writes, fork bombs).
- Output truncation: prevents context-window overflow.

### Deterministic Verifier
Enforces objective criteria:
1. `git diff` confirms non-empty modifications.
2. Build / compilation checks confirm syntactic validity.
3. Test suite execution confirms semantic correctness.
