# LaTeX Comment and Unfinished Content Register

Status legend: **Pending Review** means documented and awaiting a decision. **Applied** means a clear, authorized correction was made. **Deferred by user** means intentionally left unchanged at the user's direction. The detailed taxonomy/prompting notes have been resolved by reducing those sections to provisional plans; C1-01, C2-01, and T1-01/02/03 remain unchanged at the user's direction.

| ID | Location | Existing note/content | Classification | Finding / proposed next step | Status |
|---|---|---|---|---|---|
| C1-01 | `chap1.tex`, contribution list | `% TODO: add repository URL` | Requires author/project decision | Left unchanged at the user's direction. | Deferred by user |
| C1-02 | `chap1.tex`, organization paragraph | Obsolete `sec:*` roadmap references and TODO | Resolvable through document inspection | Replaced the broken references with existing labels `Ch:Methodology`, `Ch:EvalResults`, and `Ch:Conclusion`; retained the related-work reference. The roadmap now follows the chapters currently included in `thesis.tex`. | Applied |
| C1-03 | `chap1.tex`, scope | `\jj{Still need this}` and three “Scope to do something” bullets | Requires clarification from author | Scope must reflect agreed datasets, languages, models, task granularity, prompt conditions, and exclusions. Do not invent boundaries. | Pending Review |
| C1-04 | `chap1.tex`, expected benefits | `\jj{And this}` and placeholder benefit bullets | Requires author decision | Benefits should be modest anticipated outputs, not guaranteed empirical findings. | Pending Review |
| C1-05 | `chap1.tex`, body | “problem statement,” “objectives” prose plus preliminary claims | Academic-literature audit needed | Review claim support and construct wording after citations are checked. | Pending Review |
| C2-01 | `chap2.tex`, entire chapter | Generic template text; says chapter is optional | Requires author decision | Left unchanged at the user's direction. | Deferred by user |
| C4-01 | `chap4.tex`, Research Design | `\jj{I don't think we need this}` | Requires author decision | Consider whether the paragraph adds useful separation between behavioral/structural outcomes. It also states an important interpretation limitation. Recommend retaining that limitation somewhere if the paragraph is removed. | Pending Review |
| C4-02 | `chap4.tex`, section heading | `\jj{Name? Explanation-Guide Code Reconstruction?}` | Stylistic/terminology decision | Kept the existing heading “Explanation-Guided Reconstruction” and removed the resolved note. | Applied |
| C4-03 | `chap4.tex`, subsection heading | `\jj{Name? Test-Based ...?}` | Stylistic/terminology decision | Kept the existing heading “Behavioral Assessment” and removed the resolved note. | Applied |
| C4-04 | `chap4.tex`, subsection heading | `\jj{Name? Graph-Based ...?}` | Terminology decision | Kept the existing heading “Static Graph-Based Structural Assessment” and removed the resolved note; “static” accurately describes the AST-derived graphs. | Applied |
| C4-05 | `chap4.tex`, structural scores | `\jj{Should we include the real calculation formula?}` | Resolvable through implementation inspection and subsequent author direction | The earlier equal-weight composite matched the then-current implementation. Following the author's updated direction, the paper and implementation now report WL, alignment F1, edge Jaccard, node-label Jaccard, and control similarity separately; their calculations are unchanged and no composite is calculated or reported. Node-label Jaccard replaces the misleading operation Jaccard name because all non-function node labels are counted. | Updated |
| C4-06 | `chap4.tex`, Manual Failure Analysis | `\jj{Review this}` | Requires study-design decision | Replaced the detailed procedure with a provisional follow-on direction and stated that sampling/coding details are not finalized or implemented. | Applied |
| C4-07 | `chap4.tex`, Case Selection | `\jj{Should we have a threshold?}` | Requires author/methodology decision | Removed the proposed case-selection strata and threshold question; case selection remains explicitly unspecified in the provisional analysis paragraph. | Applied |
| C4-08 | `chap4.tex`, Root-Cause Tracing | `\jj{Review this}` | Requires study-design decision | Removed the detailed root-cause coding procedure; this direction is now explicitly provisional and no taxonomy is specified. | Applied |
| C4-09 | `chap4.tex`, failure categories | `\jj{We could use this as our failure modes, but review first and we might need to set the condition}` | Requires author decision / pilot analysis | Removed the example category list. The paper now retains only a provisional qualitative-analysis direction and states that categories are not finalized. | Applied |
| C4-10 | `chap4.tex`, prompt experiment | `\jj{Should we use this or the prompting technique from other papers?}` | Requires author decision and literature review | Removed the specific prompt paradigms and 3×3 design. The paper now describes prompting only as a provisional direction; no conditions are presented as selected or implemented. | Applied |
| C4-11 | `chap4.tex`, consistency | `\jj{how can we say that it is consistent? stat? CV for TPR and SSS? or should this be in chapter 4}` | Requires study-design decision / additional experiments | Removed the comparison/consistency section that depended on the unselected prompt matrix. Repeated-generation and statistical plans remain to be specified before those analyses. | Applied |
| C4-12 | `chap4.tex`, Behavioral Assessment | Task-level binary TPR formula | Technical consistency with implementation | Replaced the task-level average with the pooled per-input rate used by `Evaluator`; stated that tasks with more test inputs contribute more inputs to the aggregate. | Applied |
| C5-01 | `chap5.tex`, dataset rationale | Obsolete `sec:functional-check` reference and TODO | Resolvable through document inspection | Updated the reference to `sec:method-behavior`, the existing Behavioral Assessment label, and removed the resolved TODO. | Applied |
| C5-02 | `chap5.tex`, MBPP+ task count | `% TODO: confirm with the EvalPlus release notes why these tasks were removed` | Requires primary-source verification | Verify 378-task subset and exclusion rationale against official EvalPlus release/source. Do not infer removal reasons from count difference alone. | Pending Review |
| T1-01 | `thesis.tex`, document metadata | “Your Capstone Project Title in English”; `XXXXXX`, `XX88XXX`, `20XX`, generic degree/advisor fields | Requires author input | Left unchanged at the user's direction. | Deferred by user |
| T1-02 | `abstract.tex` | Generic instructions instead of project abstract | Requires author input and finalized proposal scope | Left unchanged at the user's direction. | Deferred by user |
| T1-03 | `appendixA.tex` | “Section 1 in Appendix A”, “Section B in Appendix A” | Requires author decision | Left unchanged at the user's direction. | Deferred by user |


## Approved modification log

| Issue ID | Location | Description | Status |
|---|---|---|---|
| CH1-006 | `chap1.tex`, overview/RQs/objectives/contributions | Reframed failure analysis and prompting as provisional directions; removed specific taxonomy examples and fixed prompt-design claims. | Applied |
| CH4-13 | `chap4.tex`, research design and follow-on sections | Kept only a baseline as the specified study procedure; replaced detailed failure-analysis and prompt matrices with concise provisional statements. | Applied |
| CH4-14 | `chap4.tex`, Behavioral Assessment | Replaced task-level TPR formula with the pooled per-input formula used by the implementation. | Applied |
| CH1-008 / CH3-003 | `chap1.tex`, `chap3.tex`, graph descriptions | Replaced claims of complete control-flow/data-flow graph extraction with an implementation-accurate description of the static AST-derived graph abstraction. | Applied |
| TEX-001 | `muictthesis.sty`, URL rendering | Changed visible URL text to use `\nolinkurl` inside `\href`, preventing underscores in bibliography URLs from causing a math-mode error. Rebuilt the PDF successfully. | Applied |

## Other comments

`thesis.tex` contains many template/history comments, package notes, and the commented `\input{chap2}`. They are not all editorial TODOs. The commented chapter input is a document-structure decision (C2-01), and no comment was deleted. General commented package/template code was not individually enumerated because it is not a question or unfinished research claim.


## Follow-on design update

At the user's direction, Chapter 1 and Chapter 4 now retain failure analysis and prompt investigation only as provisional research directions. The specific failure categories, case-selection strata, prompt families, 3×3 matrix, and prompt-comparison analysis were removed. The paper states that these methods have not been selected and will be specified before the corresponding investigations are conducted.


The TPR formula was also aligned with the implementation: it now divides all passing input cases by all evaluated input cases, rather than averaging binary task outcomes.


The Chapter 1 and Chapter 3 graph descriptions now match `structural_graph_utils/normalize.py` and `builder.py`: they refer to selected operations and control/data dependencies represented in normalized-AST-derived static graphs. `Image/EvaluationPipeline.png` and `Image/Methodology.png` were not modified.


## PDF citation diagnosis

`ren2020codebleu` exists in `reference.bib` and `thesis.bbl`, and `thesis.aux` maps it to bibliography number 9. The first PDF build was performed before the citation mapping had been read on a subsequent LaTeX pass. During rebuilding, a separate URL-rendering error in `muictthesis.sty` stopped XeLaTeX at an underscore in a bibliography URL. The URL macro was corrected and two XeLaTeX passes then completed successfully with no undefined citation/reference warnings.
