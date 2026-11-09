# Project Understanding

## Scope and evidence

Reviewed the root README, Python modules, `structural_graph_utils/`, notebook file inventory, data/artifact/result directory structure, the two PNG diagrams in `Image/`, and the LaTeX project entry point and chapters. This is an implementation-first reading; no experiment was run and existing result files were not treated as final evidence. The implementation root does not appear to be a Git working tree (`git status` reported that it was not a repository), so there is no Git history/status available here to establish provenance.

## Project overview

The code currently implements explanation-guided reconstruction of Python benchmark solutions. Given original code C, it prompts a configured model for a natural-language explanation E, starts a fresh model session, and asks for reconstructed code C'. It evaluates C' in two separate ways: differential execution against the original implementation over benchmark input cases, and static graph comparison between normalized AST-derived graphs of C and C'.

The README names HumanEvalPlus and MBPP+ as the data sources. Dataset rows are loaded through Hugging Face `datasets`; base and Plus inputs are loaded through EvalPlus's Python API. Local files under `data/original_code/{humaneval,mbpp}` override downloaded source solutions. Model/provider adapters exist for Claude CLI, Codex CLI, local Ollama, and a mock adapter. The current on-disk result and artifact directories contain outputs from GPT Codex and Ollama Qwen runs. They indicate prior work, not finalized experimental results.

## Implementation architecture and pipeline

1. `experiment.run` builds one configuration per model/dataset, loads tasks, resumes eligible completed tasks, and orchestrates model calls and assessments.
2. `dataset_utils.DatasetLoader` loads benchmark rows and matches each task ID to EvalPlus base/Plus input cases. It combines HumanEval prompt plus canonical solution, reads MBPP solution fields, applies local source overrides, and infers an MBPP entry point from test calls when necessary.
3. `reconstruction.Reconstruction.run` sends the original implementation to an explanation prompt, stores the explanation and prompt/response traces, kills the explanation session, and starts another session for reconstruction. The reconstruction prompt receives the explanation and an interface/entry-point constraint. It does not pass the benchmark natural-language task prompt or test inputs to reconstruction.
4. `llm.LLMClient` dispatches completion requests to CLI or HTTP provider adapters. `LLMSession.kill` clears local conversation history; this is the explicit session separation mechanism.
5. `behavior_assessment.BehaviorAssessment.run` handles each test input independently. For EvalPlus oracle inputs, it runs the reference and candidate functions and compares outputs using exact type/value rules plus numeric tolerance. It writes per-input outcomes and diagnostics to JSON. `evaluate.Evaluator` records totals and test pass rate in CSV. It treats an entire task as counts of passing test inputs; a task-level binary pass is not the primary recorded outcome.
6. `structural_assessment.StructuralAssessment` rebuilds reports from saved reconstructed code. It calls `structural_graph_utils.build_graph` and `compare_graphs`, writes graph/comparison JSON and DOT/SVG visualizations, task HTML, CSV, and run-level HTML.
7. `structural_graph_utils.normalize` normalizes selected AST constructs. `builder.GraphBuilder` creates a directed multigraph with operation, control, data-dependency, and scaffolding nodes/edges from supported Python constructs. This is a static abstraction generated from ASTs, not a runtime CFG/CDG/DFG extractor in the conventional full-program-analysis sense.
8. `structural_graph_utils.compare` computes and reports five scores separately: WL feature-vector cosine similarity (refinement levels 0–3), alignment F1 (mean of node and edge F1, with soft node credit based on matching WL levels), weighted Jaccard of edge-label triples, weighted Jaccard of all non-function node-label counts, and weighted Jaccard of branch/loop labels plus nesting depth. It also records graph sizes. No composite is calculated; the scores compare selected graph features and are not validated measures of semantic equivalence.

## Implementation-to-methodology mapping

| Methodology component | Python module/function | Input | Output/artifact | Current evidence/status |
|---|---|---|---|---|
| Dataset preparation | `dataset_utils.DatasetLoader.load`, `_load_humaneval`, `_load_mbpp`, `_evalplus_test_cases`; `experiment.prepare_dataset` | HF dataset rows, EvalPlus task dictionaries, optional local overrides | `Task` records; local original-code files | Implemented; exact downloaded version/cache provenance should be reported for reproducibility. |
| Experiment orchestration | `experiment.run`, `_make_config` | Agent/model/dataset/task selection | Per-task run plus result paths | Implemented. Supports batching/resume and run names. |
| Explanation generation | `reconstruction.Reconstruction.run`; `llm.LLMClient` | Original code C; fixed `EXPLAIN_*` prompt | Natural-language E; explanation and trace files | One fixed baseline prompt in the implementation. |
| Code reconstruction | `reconstruction.Reconstruction.run` | E and permitted entry-point/interface context in a new session | C'; reconstruction and trace files | Implemented as a separate session. The paper's former E1–E3/C1–C3 matrix has been removed; comparative prompting remains a provisional direction only. |
| Behavioral assessment | `BehaviorAssessment.run`, `_test_script`, `_execute` | Task, original code, C', one base/Plus input | Per-case pass/fail and diagnostic JSON; task totals | Implemented as differential output comparison. Not the unchanged official EvalPlus assertion harness. |
| Behavioral aggregation | `Evaluator.record/save/summary`; `experiment.summary_table` | Counts by task | CSV counts and test pass-rate summaries | Implemented; aggregate test pass rate pools test cases, so tasks with more cases contribute more weight. |
| Static graph construction | `structural_graph_utils.normalize.normalize`; `builder.build_graph` / `GraphBuilder` | Python source and entry-point hint | Directed multigraph | Implemented for supported AST constructs; unsupported syntax/entry-point conditions can be flagged. |
| Structural assessment | `compare_graphs`; `StructuralAssessment.run_task/build_report` | Original and reconstructed source | Five structural similarity scores, alignment, unmatched nodes/edges, JSON/DOT/SVG/HTML/CSV | Implemented; scores are reported separately and describe selected graph features, not semantic equivalence. |
| Manual failure analysis | No corresponding analysis stage in `experiment.run` or a manual-analysis module found | Would require C, E, C', test and graph evidence | Human-coded failure categories | Not implemented; retained in the paper only as a provisional follow-on direction. |
| Prompt paradigm experiment | Fixed prompt constants in `reconstruction.py`; no matrix in `experiment.run` | One explanation and one reconstruction prompt | One reconstruction per task/run | The former 3×3 design was removed from the paper; comparative prompting remains provisional and is not implemented in the runner. |

## Figures

- `Image/EvaluationPipeline.png` broadly depicts the C→E→C' process and two assessment branches. It labels the structural output as control/data-flow graphs and one structural similarity score; the implementation creates a custom AST-derived graph abstraction and reports five structural similarity scores separately. The diagram does not show separate-session reconstruction or the boundary that excludes task descriptions/tests from the reconstruction prompt.
- `Image/Methodology.png` includes baseline evaluation, manual failure analysis, and a nine-condition prompting phase. The first and assessment concepts broadly match the code, while the latter two are now explicitly described in the paper as provisional and are not implemented in the inspected pipeline. Its assessment labels also risk implying conventional graph extraction and a validated percentage score.
- `Image/Pipeline-Methodology.pdf` exists but was not visually inspected in this pass.

## Data, artifacts, and results

`data/original_code/` contains 165 HumanEval-named files and 379 MBPP-named files (544 total). These are local source files and do not by themselves prove the task/test totals in the draft; apparent extra files, versions, and overrides require inventory reconciliation. `artifacts/` is organized by agent/model/run/dataset and contains source, explanations, reconstructed code, traces, behavior JSON, and graph-comparison artifacts. `results/` contains CSVs and HTML summaries for GPT Codex and Ollama Qwen. Treat all such outputs as work in progress pending run/version reconciliation.

## Initial observations

- `thesis.tex` comments out `\input{chap2}`. The source has `chap2.tex` Background, but it will not appear in the compiled thesis as configured.
- In the included thesis sequence, Chapter 3 is Related Works, Chapter 4 Methodology, Chapter 5 Evaluation and Results. Chapter 1 initially used mismatched roadmap labels; these were corrected to the existing chapter labels in the approved edit.
- Resolved in the approved follow-on edit: manual failure analysis and prompt investigation are labeled provisional, and the specific taxonomy and 3×3 design were removed from the paper. Neither follow-on direction is implemented in the current runner.
- The README and default config differ on preset/model identifiers (for example, README uses names not matching current defaults). Configured identifiers and recorded outputs should be reconciled before proposal claims about the study matrix.
- Current model configurations are mutable through environment variables; reproducibility needs actual resolved model IDs, versions/digests, prompts, and run settings, not just preset names.
- The current structure metric uses static graph features and hand-set equal weights. It supports a structural comparison claim; it does not alone establish explanation faithfulness, semantic completeness, or general program equivalence.


## Update after proposal-scope decision

The thesis now describes manual failure analysis and prompt investigation as provisional follow-on directions. Their specific categories, sample selection, prompt families, factorial design, and comparative analysis plan have been removed pending the user's later decisions. The implementation remains baseline-only for these purposes.


The approved text edit updated Chapter 1 and Chapter 3 to describe the custom normalized-AST static graph representation and its selected features. The two PNG diagrams remain unchanged and are tracked as terminology-review items.
