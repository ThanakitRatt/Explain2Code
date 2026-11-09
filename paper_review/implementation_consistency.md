# Implementation–Paper Consistency Register

This register compares the current draft with source code inspected in the workspace. “Implemented” describes code presence, not validity or successful completion of every run. No source or paper files were changed.

| Paper statement/component | Implementation evidence | Consistency assessment | Needed clarification |
|---|---|---|---|
| C→E→C' explanation-guided reconstruction | `reconstruction.py`: `Reconstruction.run`; `llm.py`: new sessions and `LLMSession.kill` | Broadly consistent | Identify exact prompt texts and permitted entry-point context. State that reconstruction is isolated in a new session and does not receive benchmark prompt/test cases. |
| Dataset/task loading | `dataset_utils.py`: `DatasetLoader`, HF load and EvalPlus input API | Broadly consistent | Dataset versions/splits and exact snapshot need recording. Local source overrides mean the actual `C` can differ from the downloaded source. |
| HumanEval+ and MBPP+ behavioral assessment | `behavior_assessment.py`: `run`, `_test_script`, `_execute` | Partially consistent | Implementation compares original vs reconstructed output separately for each base/Plus input; it does not run the unmodified official EvalPlus assertion harness. Tests are isolated subprocesses with configured timeout. |
| “Test Pass Rate” | `BehaviorAssessment.run`; `Evaluator.record/summary`; `experiment.summary_table` | Consistent after approved revision | Chapter 4 now defines TPR as pooled passing inputs divided by all evaluated inputs and states the implied per-input weighting. |
| Numeric tolerance | `BehaviorAssessment` oracle script | Partially consistent | Uses `math.isclose(rel_tol=1e-7, abs_tol=task.atol)` for floats; booleans are checked separately and nested structures recursively. Draft says numeric outputs use implementation tolerances but omits relative tolerance. |
| Graph representation terminology | `structural_graph_utils/normalize.py`, `builder.py` | Consistent after approved revision in Chapters 1 and 3 | Paper now calls this a custom static graph representation built from normalized Python ASTs, encoding selected operations and control/data dependencies; it notes that this is narrower than complete CFG/DFG analysis. Diagram labels remain to be reviewed. |
| Five structural similarity scores | `structural_graph_utils/compare.py`: `wl_iterations`, `align_nodes`, `compare_graphs` | Updated to report five scores separately | WL levels are 0–3; alignment F1 averages node and edge F1; edge Jaccard, node-label Jaccard, and control similarity retain their existing calculations. Node-label Jaccard counts all non-function node labels. No composite is calculated or reported. These custom scores compare selected features of the AST-derived graph and are not validated measures of semantic equivalence. |
| Manual failure analysis | No analysis stage in `experiment.run` or manual-analysis module; Chapter 4 now labels this a provisional follow-on direction | Original code, explanation, reconstruction, and assessment artifacts | Possible human-coded case analysis; protocol undecided | Not implemented; paper no longer presents a specific method or completed analysis. |
| Failure taxonomy | No implementation found; specific category list removed from Chapter 4 | To be determined if follow-on analysis is undertaken | No fixed taxonomy | Not implemented or selected; retained only as a possibility in Chapter 1. |
| Prompting investigation | `reconstruction.py` has one fixed explanation and reconstruction prompt; `experiment.run` has no condition matrix | Original code and baseline prompt workflow | Alternative prompt conditions remain undecided | No comparative prompt study is implemented; Chapter 4 now labels this only as provisional and specifies no prompt families or design. |
| Structural reports/artifacts | `StructuralAssessment.run_task/build_report`; `structural_graph_utils.render` | Implemented | Reports are regenerated from saved reconstructed code. A parse error can prevent a structural score; report denominators/failed cases should be explicit. |
| Model comparison | `config.py` presets; `experiment.run_all`; result folders | Partially implemented/configuration unclear | README preset names do not match current `config.py` defaults. IDs can be environment overrides. Report resolved IDs and versions, and distinguish prior outputs from planned matrix. |
| Reproducibility records | artifacts and CSV include prompt/response traces, source/reconstruction, configured model, time, test suite version | Partially implemented | Confirm provider/CLI versions, actual local model digest, environment and exact prompt condition are captured for every run. Do not claim complete version capture without evidence. |

## Key source locations

- Orchestration: `experiment.py` (`run`, `run_all`, `prepare_dataset`)
- Configuration: `config.py` (`AGENT_PRESETS`, `DatasetConfig`, `LLMConfig`, `PipelineConfig`)
- Dataset loading: `dataset_utils.py` (`DatasetLoader`)
- Model I/O: `llm.py` (`LLMSession`, `LLMClient`)
- Prompting/reconstruction: `reconstruction.py` (`EXPLAIN_TEMPLATE`, `GENERATE_TEMPLATE`, `Reconstruction.run`)
- Behavioral tests and scoring: `behavior_assessment.py`; aggregation: `evaluate.py`
- Graph abstraction/comparison: `structural_graph_utils/normalize.py`, `builder.py`, `compare.py`
- Reports: `structural_assessment.py`, `structural_graph_utils/render.py`
