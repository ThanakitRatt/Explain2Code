# Citation Audit — Initial Inventory and Verification Queue

## Status

No publication has yet been classified as **VERIFIED AND SUPPORTED**. This pass inventories citation keys and their surrounding role but does not establish bibliographic accuracy or claim support. The next citation-audit pass must verify metadata against publisher/proceedings/arXiv/institutional sources and inspect the specific supporting claims. The `.bib` keys are not evidence of publication correctness.

## Inventory

All 34 unique in-text citation keys found in the LaTeX files have a matching BibTeX key in `reference.bib`. Three bibliography entries were not found in any in-text citation: `smith2024`, `parker2020`, and `example2024website`; determine whether they are intentional before removing anything. Citation commands in commented material may affect this inventory.

| Key | Draft role / claim context | Initial status |
|---|---|---|
| `10.1109/SP.2014.44` | Code Property Graphs and graph traversal for vulnerability discovery | UNVERIFIED |
| `abdollahi2025demystifying` | Taxonomy of errors in model code-execution reasoning; edge cases | UNVERIFIED |
| `allamanis2018graphs` | Program representations using syntax/data/control flow | UNVERIFIED |
| `allamanis2024rtc` | Round-trip correctness: explain code, regenerate, test; correlation claim | UNVERIFIED |
| `anthropicClaudeCodeWorkflows` | Bibliography only or outside audited chapter context | UNVERIFIED |
| `austin2021programsynthesislargelanguage` | MBPP benchmark description | UNVERIFIED |
| `chen2021evaluatinglargelanguagemodels` | HumanEval description and task count | UNVERIFIED |
| `chen2024selfdebug` | Self-Debug method and claimed effect | UNVERIFIED |
| `crupi2025judge` | LLM judge reliability for code and summaries | UNVERIFIED |
| `du2024classeval` | ClassEval scope/performance comparison | UNVERIFIED |
| `fang2026evalooopselfconsistencycenteredframeworkassessing` | EvaLoop loop-until-failure procedure and ranking claim | UNVERIFIED |
| `gao-etal-2026-core` | CoRE intermediate-state reasoning claim | UNVERIFIED |
| `googleMbppDatasetCard` | Sanitized MBPP task count/context | UNVERIFIED |
| `le2025names` | Identifier removal and code-summary claim | UNVERIFIED |
| `liu2023evalplus` | EvalPlus methodology, suite sizes, benchmark changes | UNVERIFIED |
| `liu2024codemind` | Relationship between code generation and reasoning | UNVERIFIED |
| `luo-etal-2024-repoagent` | Related-work bibliography; locate cited passage | UNVERIFIED |
| `min2024beyond` | IdentityChain setup and self-consistency outcome | UNVERIFIED |
| `olausson2024selfrepair` | Self-repair gains/limitations | UNVERIFIED |
| `ollamaOfficial` | Related-work bibliography or system details | UNVERIFIED |
| `openai2025introducingcodex` | Related-work bibliography or agent context | UNVERIFIED |
| `openaiHumanEvalDatasetCard` | HumanEval dataset fields and task count | UNVERIFIED |
| `parcalabescu2024faithfulness` | Faithfulness tests vs self-consistency; measure limitations | UNVERIFIED |
| `pizzorno2025coverup` | Related-work bibliography; locate cited passage | UNVERIFIED |
| `pmlr-v235-gu24c` | CRUXEval input/output prediction tasks and findings | UNVERIFIED |
| `ren2020codebleu` | CodeBLEU component/limitation claims | UNVERIFIED |
| `sennrich2016backtranslation` | Back-translation origin/context | UNVERIFIED |
| `shervashidze2011wl` | Weisfeiler–Lehman graph kernel procedure | UNVERIFIED |
| `shinn2023reflexion` | Reflexion verbal reflection and memory | UNVERIFIED |
| `wei-etal-2025-equibench` | Equivalence benchmark findings about syntactic reliance | UNVERIFIED |
| `xie2026core` | CoRe static-analysis dependency/control-flow claim | UNVERIFIED |
| `yang2024sweagent` | Related-work bibliography; locate cited passage | UNVERIFIED |
| `zhang2024autocoderover` | Related-work bibliography; locate cited passage | UNVERIFIED |
| `zhuo2025bigcodebench` | BigCodeBench scope and task characteristics | UNVERIFIED |

## Priority verification concerns

1. Chapter 1 makes broad novelty/gap statements (“none of these approaches,” “unknown failure modes”) that require systematic support and appropriately bounded wording.
2. Chapter 3 contains detailed claims about benchmark sizes, rankings, correlations, failure rates, and limitations. Verify results from full texts, not abstracts alone.
3. The EvalPlus method and dataset task statistics are central to the proposal and should be checked against the original paper/release and the precise benchmark snapshot used.
4. Several cited items are dated 2026. Confirm publication/preprint status and metadata as of the intended submission date.
5. Verify every DOI/URL field against the publication record; do not infer an identifier from a BibTeX key.

No references were added, removed, or corrected.
