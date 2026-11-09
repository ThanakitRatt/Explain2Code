# Code Reconstruction and Explainability Replication Package

This repository contains the implementation and experiment materials for a study of whether a coding agent can reconstruct a program from a natural-language explanation of that program. It is intended for researchers who want to inspect the method, rerun the pipeline with their own model access, or examine the saved benchmark inputs and results.

## What the experiment does

For each selected benchmark task, the pipeline:

1. Loads the reference program and task metadata from HumanEval+ or MBPP+.
2. Asks a selected coding agent to explain the reference program (code → explanation).
3. Ends that model session, then asks the agent to reconstruct a program using the explanation (explanation → reconstructed code).
4. Executes the benchmark's base and Plus test inputs against the reconstruction and records the number passed and total.
5. Compares semantic program graphs for the reference and reconstruction, then writes structural metrics and HTML reports.

Behavioral results are test pass counts and rates; they are not a claim of full correctness. Structural metrics are a separate comparison of normalized program graphs. The structural stage uses the saved behavior assessment and does not run a second behavioral test suite.

## Replication package contents

```text
.
├── L1-RunExperiment.ipynb       # Notebook entry point and experiment examples
├── config.py                    # Dataset, model, path, and timeout configuration
├── experiment.py                # Public experiment.run(...) API and result index
├── dataset_utils.py             # Hugging Face and EvalPlus data loading
├── llm.py                       # Claude CLI, Codex CLI, Ollama, and mock clients
├── reconstruction.py            # Explanation and reconstruction prompts/stages
├── behavior_assessment.py       # Per-input execution and behavioral results
├── structural_assessment.py     # Graph comparison and report generation
├── structural_graph_utils/      # AST normalization and graph scoring/rendering
├── requirements.txt             # Python package dependencies
├── data/original_code/          # Cached benchmark reference solutions
├── artifacts/                   # Generated prompts, outputs, traces, and reports
├── results/                     # Generated CSV/HTML summaries
└── paper_review/                # Project and manuscript review notes
```

`data/original_code/{humaneval,mbpp}/` contains benchmark reference code that has been cached or prepared in this checkout. Existing files in those folders override the corresponding downloaded reference, so keep local edits deliberate. Hugging Face task records and EvalPlus base/Plus inputs are also downloaded and cached by their libraries on first use. EvalPlus `plus_input: {}` means there are no additional Plus cases for that task. The Hugging Face assertion examples are not counted again; the evaluation uses the official EvalPlus input sets.

Generated run files are organized by agent, model, optional run name, and dataset:

```text
artifacts/{agent}/{model}/{run_name?}/{dataset}/
  original_code/ explanation/ reconstructed_code/ test_results/
  trace/ errors/ structural_assessment/
results/{agent}/{model}/{run_name?}/{dataset}/
  behavior_assessment.csv structural_assessment.csv
results/{agent}/{model}/{run_name?}/structural_report.html
results/index.html
```

The Python dependencies and benchmark sources are downloaded during setup or the first dataset preparation. Model services and CLIs are not bundled. Running an actual experiment therefore requires network access for dataset downloads and access to at least one supported model provider. The mock provider is useful for checking orchestration, but it does not produce meaningful model results.

## Requirements and environment notes

- Python 3.11 is the recommended baseline. Use a separate environment; the repository's `.venv` is machine-local and should not be reused after cloning.
- macOS, Linux, and Windows are suitable for the Python pipeline. On Windows, use WSL2 for the smoothest experience with Jupyter and command-line model providers; native PowerShell commands are provided below for Python setup.
- The package does not require a GPU. If you run a local Ollama model, model speed and memory needs depend on the selected model and machine.
- You need Git, a working Python/pip installation, and Internet access for the initial package and benchmark downloads.
- Choose one model backend: Claude Code CLI, OpenAI Codex CLI, or Ollama. Install and authenticate/download models using the provider's current instructions. Provider availability, model names, account access, and CLI options can change; use model IDs accepted by the version you installed.

## Clone and install

Run commands from the cloned project root (the directory containing this README). Substitute your repository URL as needed.

### macOS or Linux (venv)

```bash
git clone <repository-url>
cd <repository-directory>
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name reconstruction-pipeline \
  --display-name "Python (Reconstruction Pipeline)"
```

On macOS, install Python 3.11 through your preferred package manager if `python3.11` is not available. On Linux, use the distribution's Python 3.11 package or another trusted Python installation method.

### Windows (PowerShell)

```powershell
git clone <repository-url>
Set-Location <repository-directory>
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name reconstruction-pipeline --display-name "Python (Reconstruction Pipeline)"
```

If PowerShell blocks environment activation, either use the documented execution-policy procedure for your organization or run the environment's interpreter directly (`.venv\Scripts\python.exe -m pip ...`). WSL2 users should follow the macOS/Linux commands inside their Linux distribution.

### Conda alternative (all platforms)

```bash
conda create -n reconstruction-pipeline python=3.11 -y
conda activate reconstruction-pipeline
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name reconstruction-pipeline \
  --display-name "Python (Reconstruction Pipeline)"
```

On Windows Conda Prompt, enter the commands without the line-continuation backslashes. Do not install packages into the system Python unless that is intentional.

## Configure a model provider

Install and configure at least one provider before starting a real run. The command-line binary must be on `PATH`, or set its binary environment variable (`CLAUDE_BIN` or `CODEX_BIN`). The corresponding CLI must be authenticated according to its own instructions. For Ollama, start its local service, pull a model, and keep the service running; the default OpenAI-compatible URL is `http://localhost:11434/v1` and can be changed with `OLLAMA_BASE_URL`.

The presets are declared in `config.py`:

- `claude_code`: `opus`, `sonnet`, `haiku`
- `gpt_codex`: `astra`, `sol`, `luna`
- `ollama_qwen`: `qwen2.5-coder-3b`, `qwen3.5-9b`, `qwen2.5-coder-14b`
- `mock`: `offline` (pipeline/orchestration only)

Preset keys map to model IDs in `config.py`; override an ID with the environment variables listed below if your provider uses different names or the default is unavailable. A configured preset is not a guarantee that your account, installed CLI, or local server offers that model. Check the provider's own model list and supply an accepted ID.

For Ollama, for example, pull the exact model tag configured in `config.py` (or override it):

```bash
ollama pull qwen2.5-coder:3b
```

## Prepare data and launch

1. From the project root, activate the environment you created above.
2. Start Jupyter Lab:

   ```bash
   jupyter lab L1-RunExperiment.ipynb
   ```

   On Windows, this command is the same in an activated PowerShell or Conda Prompt.
3. In the notebook, select the **Python (Reconstruction Pipeline)** kernel (or the environment's Python kernel).
4. Run the notebook's setup/import cells. To download and cache benchmark sources without invoking a model, run:

   ```python
   import experiment
   experiment.prepare_dataset(("humaneval", "mbpp"))
   ```

5. Choose an agent, model key, and dataset in the notebook. Start with a small `limit` while checking model access and output. Then remove the limit for the full dataset if desired.
6. Run the experiment. Each task's results are saved as it completes, so an interrupted run can resume with the same configuration and run name.
7. Open `results/index.html` for the generated overview. The behavior and structural CSVs and structural HTML reports are also stored under the result/artifact paths shown above.

The notebook is the documented interface. The core API is `experiment.run(agent=..., model_key=..., datasets=(...), limit=..., batch_size=..., run_name=...)`; `experiment.run_all(...)` iterates over the configured model matrix and may incur substantial time or provider usage. Set either `limit` or `batch_size`, not both. A named run keeps separate outputs; use the same name to resume it. Without a name, runs use the default agent/model/dataset folder. Completed tasks resume by default when their saved test-suite version and test count match.

## Reproducibility and interpretation

- Record the repository revision, Python version, operating system, package versions, provider/CLI version, exact model ID, dataset/split, run name, and any environment overrides alongside reported results. Model APIs and model outputs can change over time, so a rerun may not reproduce identical generated code even with the same source revision.
- By default, datasets are `evalplus/humanevalplus` and `evalplus/mbppplus`, using their `test` splits. Benchmark task aliases are `humaneval` and `mbpp`.
- Per-task `behavior_assessment.json` records outcomes for individual base and Plus inputs. The behavior CSV reports passed/total counts and pass rate. Test timeouts default to 15 seconds per input; agent request timeouts default to 900 seconds.
- A task failure is recorded with an error and does not stop later tasks. Review error artifacts and provider output before interpreting aggregate metrics.
- Structural scores are calculated from normalized graph representations by this package. Review the saved graph, alignment, and HTML task reports when interpreting individual comparisons.
- The first preparation/run may take longer while dependencies, benchmark data, and model weights are downloaded. Local model latency and resource needs depend on the machine and selected model.

## Configuration reference

Set environment variables before launching Jupyter so the notebook kernel inherits them. In PowerShell use `$env:NAME = "value"`; in Bash/zsh use `export NAME="value"`.

| Variable | Purpose |
| --- | --- |
| `CLAUDE_BIN`, `CODEX_BIN` | CLI executable path if it is not found on `PATH` |
| `CLAUDE_OPUS_MODEL`, `CLAUDE_SONNET_MODEL`, `CLAUDE_HAIKU_MODEL` | Claude model ID overrides |
| `CODEX_ASTRA_MODEL`, `CODEX_SOL_MODEL`, `CODEX_LUNA_MODEL` | Codex model ID overrides |
| `QWEN_25_CODER_3B_MODEL`, `QWEN_35_9B_MODEL`, `QWEN_25_CODER_14B_MODEL` | Ollama model tag overrides |
| `OLLAMA_BASE_URL` | Ollama OpenAI-compatible endpoint |
| `HUMANEVALPLUS_DATASET_ID`, `MBPPPLUS_DATASET_ID` | Hugging Face dataset IDs |
| `HUMANEVALPLUS_SPLIT`, `MBPPPLUS_SPLIT` | Dataset splits (default `test`) |
| `PIPELINE_DATA_ROOT` | Data and cached reference-code root |
| `PIPELINE_ARTIFACT_ROOT`, `PIPELINE_RESULT_ROOT` | Generated artifact and result roots |
| `PIPELINE_TEST_TIMEOUT_SEC` | Timeout per test input (default `15`) |
| `PIPELINE_AGENT_TIMEOUT_SEC` | Timeout per model request (default `900`) |
| `PIPELINE_MAX_TOKENS` | Maximum response length (default `2048`) |

## Troubleshooting

- **Import error after installing packages:** confirm Jupyter is running from the activated environment and the selected notebook kernel points to that environment; restart the kernel after package changes.
- **Dataset download or cache errors:** check Internet access, Hugging Face availability, and dataset ID/split settings. Re-run `prepare_dataset` after correcting the configuration.
- **CLI not found:** verify the provider CLI works in a terminal and is on `PATH`; otherwise set `CLAUDE_BIN` or `CODEX_BIN` before starting Jupyter.
- **Model unavailable or authentication error:** confirm provider login and use an exact model ID accepted by your installed provider. Change the preset override in the environment or `config.py`.
- **Ollama connection refused:** start Ollama, check `OLLAMA_BASE_URL`, and confirm the requested model is pulled locally.
- **Slow or timed-out generation:** use a smaller local model or increase `PIPELINE_AGENT_TIMEOUT_SEC`. Large local models can take several minutes to load or answer.
- **A result row is not resumed:** rows with an error, an older test-suite version, or a different expected test count are intentionally eligible to run again.

## License and citation

Add the project license and the study's canonical citation here before public release. The repository snapshot inspected for this README did not contain a license or complete citation metadata, so none is asserted here. Follow the source benchmark and model providers' terms when redistributing their data or using their services.
