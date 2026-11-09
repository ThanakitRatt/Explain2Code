# Proposal Submission Checklist

Status as of this initial review: **Not ready for submission**. This is an initial checklist, not a final compilation/readiness audit.

## Proposal content

- [ ] Replace thesis title, author, ID, academic year, advisor, and other template metadata in `thesis.tex`.
- [ ] Replace `abstract.tex` instructional placeholder with an approved abstract.
- [ ] Complete Chapter 1 scope and expected benefits; remove placeholder bullets only after approval.
- [ ] Resolve whether Chapter 2 Background is required and either include a completed chapter or update the document plan. It is currently commented out in `thesis.tex`.
- [x] Present failure analysis and prompting as provisional directions without implying that specific methods or conditions are selected or implemented.
- [ ] Specify case selection, failure coding, prompt conditions, and comparison methods before conducting those follow-on investigations.
- [x] Define TPR consistently with implementation as pooled passing inputs divided by total evaluated inputs.
- [x] Describe the graph representation in Chapters 1 and 3 as a custom AST-derived static abstraction and limit claims to its selected features.
- [ ] Review the unchanged diagram labels for the same terminology and avoid implying a validated semantic-equivalence score.
- [ ] Verify dataset counts/statistics against a fixed release and documented computation. Do not use current outputs as finalized model results.
- [ ] Decide and document repeated-run plan, prompt conditions, task sampling, and any statistical analyses before making inferential claims.

## Citations and references

- [ ] Verify every bibliographic field and identifier against original publication sources.
- [ ] Verify each cited sentence/paragraph is supported by the publication text.
- [ ] Review uncited BibTeX keys (`smith2024`, `parker2020`, `example2024website`).
- [ ] Resolve repository/replication-package availability statement.

## LaTeX structure

- [x] Fix known Chapter 1 roadmap references; final label/reference check remains for the submission build.
- [x] Corrected the dataset section reference to `sec:method-behavior`; review remaining dataset TODOs and verify labels in the final build.
- [ ] Decide whether appendix placeholders are needed.
- [ ] Confirm correct figure/table paths and captions; inspect `Image/Pipeline-Methodology.pdf` if it is intended for use.
- [x] Rebuilt with XeLaTeX after the authorized fixes; no undefined citation/reference warnings remain.
- [ ] Review remaining layout/font warnings and complete the full submission-readiness check.

## Human review/change control

- [x] Applied only clear, user-authorized cross-reference and resolved-heading-note fixes; details are in `comment_resolution.md`.
- [x] No implementation edits applied.
- [ ] Review remaining findings and decide on study-design questions before changing those parts of the paper.
- [ ] No Git status/history is available in this workspace root; a file-level backup was made before the approved LaTeX edits.
