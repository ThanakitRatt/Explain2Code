# Initial Paper Audit

## Overall assessment

The draft has a coherent central idea: use explanation-guided reconstruction, behavioral comparison, and structural comparison to study what an AI coding agent preserves about a given implementation. The proposal is not submission-ready in its current state. Chapter 1 contains template text and unfinished scope/benefit sections; the Background chapter is excluded from the thesis build; methodology claims exceed the inspected implementation; and chapter references/labels appear inconsistent. At initial review, the prompt experiment and manual failure analysis lacked an implemented-versus-planned distinction; this was addressed in the approved follow-up edit. No paper files were edited during the initial audit; subsequent user-approved changes are recorded below.

## Critical findings

- **Provisional methodology (Chapter 4 / `chap4.tex`):** the inspected runner implements the baseline explanation/reconstruction workflow but no manual failure analysis or comparative prompt study. The approved revision now labels both as provisional follow-on directions and removes the specific failure categories and 3×3 prompt matrix.
- **Evaluation construct claims need calibration (Chapters 1, 3, 4):** test agreement on finite benchmark inputs and custom AST-derived graph scores do not establish full semantic understanding, explanation faithfulness, or equivalence. Some objectives use “semantic fidelity and completeness”; the five graph scores are not validated measures of semantic equivalence. Claims and outcomes need a clear operational definition and limitation.
- **Proposal front matter and Chapter 1 are unfinished:** `thesis.tex` retains title, author, academic year, degree/advisor metadata placeholders. `chap1.tex` includes instructional template prose, unresolved `\jj{}` notes, and placeholder scope/benefit bullets.
- **Background chapter omitted:** `thesis.tex` comments out `\input{chap2}`; `chap2.tex` contains only generic template text and says it is optional. The compiled document therefore jumps from Introduction to Related Works.

## Major findings

- Chapter 1's roadmap points to labels that do not match the current chapter labels. Inspect all `\ref`/`\label` pairs and undefined citation/reference warnings during a later approved readiness pass.
- The initial TPR formula conflicted with the implementation, which pools individual passing and total inputs. The approved revision aligned the formula and stated its per-input weighting.
- Chapter 1 and Chapter 3 initially described the implementation as extracting control-flow and data-flow graphs. Approved revisions now describe the custom static, normalized AST-derived graph representation and its selected operations/dependencies. The diagrams still use control/data-flow graph wording and should be reviewed; they were not changed.
- `chap5.tex` includes dataset counts and structural statistics, but the local files alone do not verify the reported counts or all derived statistics. Some rows may be local overrides; verify from the exact HF/EvalPlus release and statistics script/output before relying on them.
- `README.md` and `config.py` contain differing model preset names/IDs. Actual run metadata and proposal scope need reconciliation.
- The study's consistency/reproducibility claims are still decisions in progress. Current run records contain a configured model string and elapsed time; recording resolved software versions, model digests, repeated generations, and condition-specific prompt text should be checked against artifacts before claiming they are captured.

## Minor / editorial findings

- Remove or replace template prose in `chap2.tex`, Chapter 1 scope/benefits, and abstract only after author approval.
- Review section names and headings noted by `\jj{}` in `chap4.tex`.
- Ensure metric naming is consistent: “Test Pass Rate” and the five separately reported structural similarity scores (SSS) should be distinguished throughout.
- The draft contains comments/TODOs about repository URL, outdated section references, dataset task removal rationale, and methodology decisions. See `comment_resolution.md`.

## Chapter status

| Chapter/source | Current role | Initial status |
|---|---|---|
| `chap1.tex` | Introduction | Major unfinished sections and template remnants; research motivation/objectives exist but claims need scope alignment. |
| `chap2.tex` | Background | Generic template only and omitted from `thesis.tex`; no usable technical background chapter yet. |
| `chap3.tex` | Related Works | Substantial topical structure, but citation-to-claim verification and gap substantiation remain outstanding. |
| `chap4.tex` | Methodology | Baseline procedure is described; failure analysis and prompt investigation are provisional. TPR now matches the pooled per-input calculation. The remaining diagram terminology and implementation details still need review. |
| `chap5.tex` | Evaluation and Results | Dataset section has detailed statistics and TODOs; user priority allows review of dataset sections only. Other evaluation/results content is out of scope unless requested. |
| `chap6.tex` | Conclusion/Future Work | Not audited beyond file organization; out of immediate proposal priority. |

## Citation audit status

No publication metadata or claim support is marked verified in this initial pass. `citation_audit.md` lists keys/required verification work. A source appearing relevant by title or citation context is not proof of support. Citation claims in Chapters 1 and 3 should be audited against original publications before being treated as established.

## Review/change log

The initial audit was findings-only. Approved changes and their status are recorded in the updates below and in `comment_resolution.md`; remaining substantive revisions are still pending.


## Update after user direction

The user confirmed that the failure taxonomy and prompting paradigm are still under consideration and may be decided after the proposal presentation/submission. They also directed that C1-01, C2-01, and T1-01/02/03 remain unchanged. The broken Chapter 1 roadmap references and Chapter 5 behavioral-assessment reference were corrected; resolved heading/formula notes in Chapter 4 were removed while retaining the existing headings and formula. No decision has been made about how to scope the taxonomy/prompting material in the proposal.


## Update after provisional-design decision

The user asked to retain failure analysis and prompt investigation as provisional plans while removing the specific taxonomy and prompting details. Chapter 1 RQ/objective/contribution wording and Chapter 4 design text were updated accordingly. The case-selection strata, failure category list, E1–E3/C1–C3 prompts, 3×3 matrix, and prompt-pair consistency analysis were removed. The proposal now states that these methods are unselected and will be specified before any follow-on investigation. The implementation still contains only the baseline prompt workflow; no manual analysis or comparative prompt experiment was added.


## Graph-description precision update

Chapters 1 and 3 were revised to describe the implementation as a custom static graph representation built from normalized Python ASTs, encoding selected operations and control/data dependencies. The text no longer claims that the implementation extracts complete conventional control-flow/data-flow graphs or that graph differences alone identify what an explanation omitted. The PNG diagrams remain unchanged pending review.
