# ACTP Methodology

## 1. Research Questions

### Primary Research Question
Can an adaptive, outcome-aware tool planner reduce the number of repository-tool calls, token consumption, and execution time required by an autonomous coding agent while preserving verified task correctness?

### Secondary Research Questions
1. Does planning a tool sequence outperform selecting each tool independently?
2. Does observing tool outcomes improve subsequent tool selection?
3. Can the system detect low-value or repeated tool actions?
4. Does an explicit budget improve efficiency?
5. How much efficiency can be gained without reducing task success?
6. When should the planner stop exploring and begin implementation?
7. When should the planner replan after a failed action?

---

## 2. Hypotheses

- **H1 — Efficiency**: ACTP will require fewer tool calls than a baseline coding agent on comparable tasks.
- **H2 — Token Efficiency**: ACTP will consume fewer input/output tokens while maintaining comparable task success.
- **H3 — Execution Efficiency**: ACTP will reduce unnecessary repository commands and execution time.
- **H4 — Failure Recovery**: ACTP will reduce repeated ineffective tool calls after failed actions.
- **H5 — Correctness Preservation**: The reduction in resource consumption will not significantly reduce verified task completion.

---

## 3. Baselines for Comparison

1. **Baseline A — Naive ReAct**: The agent sees the full toolset and selects tools greedily using raw prompt reasoning, without cost-weighting, budget checks, or repetition damping.
2. **Baseline B — Fixed Tool Order**: Executes a rigid sequence (`find_files` $\to$ `grep` $\to$ `read_file` $\to$ `edit_file` $\to$ `run_tests`) regardless of outcome feedback.
3. **Baseline C — Static Router**: Routes based on task-type classification at the beginning, but does not observe outcome progress or replan dynamically.
4. **ACTP (Proposed System)**: Full adaptive tool planner with online cost estimation, repetition detection, outcome-aware replanning, and deterministic verification.

---

## 4. Ablation Study Framework

To isolate the exact causal factors contributing to efficiency gains:
- **Ablation 1**: ACTP without budget awareness.
- **Ablation 2**: ACTP without outcome history.
- **Ablation 3**: ACTP without repetition penalty.
- **Ablation 4**: ACTP without tool-cost estimates.
- **Ablation 5**: ACTP without task-type priors.
- **Full ACTP**: All components enabled.

---

## 5. Metrics & Composite Score

### Raw Metrics
- **Success Rate**: $\frac{\text{Successful Tasks}}{\text{Total Tasks}}$
- **Tool Calls**: Total tool invocations
- **Tokens**: Total input + output tokens
- **Execution Time**: Wall-clock seconds
- **Failed Tool Calls**: Number of tool failures / timeouts
- **Repeated Actions**: Consecutive redundant actions

### Composite Efficiency Metric
$$\text{Efficiency} = \frac{\text{SuccessRate}}{1 + \alpha \text{NormTokens} + \beta \text{NormCalls} + \gamma \text{NormTime}}$$
Where reference normalizers prevent metric scale skewing.
