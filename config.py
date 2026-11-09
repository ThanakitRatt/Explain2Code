"""Central paths, benchmark identifiers, and coding-agent model presets."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("PIPELINE_DATA_ROOT", PROJECT_ROOT / "data")).expanduser()
ARTIFACT_ROOT = Path(
    os.getenv("PIPELINE_ARTIFACT_ROOT", PROJECT_ROOT / "artifacts")
).expanduser()
RESULT_ROOT = Path(os.getenv("PIPELINE_RESULT_ROOT", PROJECT_ROOT / "results")).expanduser()
TEST_SUITE_VERSION = "evalplus-base-plus-v1"


def resolve_binary(env_var: str, command: str) -> str:
    return os.getenv(env_var) or shutil.which(command) or command


@dataclass(frozen=True)
class AgentPreset:
    provider: str
    models: dict[str, str]
    binary: str = ""
    base_url: str = ""


# Model IDs are deliberately editable: use the exact IDs accepted by your
# installed CLI/Ollama server if its naming differs.
AGENT_PRESETS = {
    "claude_code": AgentPreset(
        provider="claude_cli",
        binary=resolve_binary("CLAUDE_BIN", "claude"),
        models={
            "opus": os.getenv("CLAUDE_OPUS_MODEL", "claude-opus-5.5"),
            "sonnet": os.getenv("CLAUDE_SONNET_MODEL", "claude-sonnet-5.5"),
            "haiku": os.getenv("CLAUDE_HAIKU_MODEL", "claude-haiku-5.5"),
        },
    ),
    "gpt_codex": AgentPreset(
        provider="codex_cli",
        binary=resolve_binary("CODEX_BIN", "codex"),
        models={
            "astra": os.getenv("CODEX_ASTRA_MODEL", "gpt-6-astra"),
            "sol": os.getenv("CODEX_SOL_MODEL", "gpt-6-sol"),
            "luna": os.getenv("CODEX_LUNA_MODEL", "gpt-6-luna"),
        },
    ),
    "ollama_qwen": AgentPreset(
        provider="ollama",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        models={
            "qwen2.5-coder-3b": os.getenv("QWEN_25_CODER_3B_MODEL", "qwen2.5-coder:3b"),
            "qwen3.5-9b": os.getenv("QWEN_35_9B_MODEL", "qwen3.5:9b"),
            "qwen2.5-coder-14b": os.getenv("QWEN_25_CODER_14B_MODEL", "qwen2.5-coder:14b"),
        },
    ),
    "mock": AgentPreset(provider="mock", models={"offline": "mock"}),
}


@dataclass
class DatasetConfig:
    """Benchmark aliases stay `humaneval` and `mbpp`; sources use Plus data."""

    name: str = "humaneval"
    humaneval_hf_id: str = os.getenv("HUMANEVALPLUS_DATASET_ID", "evalplus/humanevalplus")
    mbpp_hf_id: str = os.getenv("MBPPPLUS_DATASET_ID", "evalplus/mbppplus")
    humaneval_config: str | None = None
    mbpp_config: str | None = None
    humaneval_split: str = os.getenv("HUMANEVALPLUS_SPLIT", "test")
    mbpp_split: str = os.getenv("MBPPPLUS_SPLIT", "test")
    limit: int | None = None


@dataclass
class LLMConfig:
    agent: str = "mock"
    provider: str = "mock"
    model: str = "mock"
    binary: str = ""
    base_url: str = ""
    timeout_sec: int = int(os.getenv("PIPELINE_AGENT_TIMEOUT_SEC", "900"))
    temperature: float = 0.2
    max_tokens: int = int(os.getenv("PIPELINE_MAX_TOKENS", "2048"))


@dataclass
class PipelineConfig:
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    data_root: Path = DATA_ROOT
    artifact_root: Path = ARTIFACT_ROOT
    result_root: Path = RESULT_ROOT
    test_timeout_sec: int = int(os.getenv("PIPELINE_TEST_TIMEOUT_SEC", "15"))
    run_name: str = ""

    def __post_init__(self) -> None:
        self.data_root = Path(self.data_root).expanduser()
        self.artifact_root = Path(self.artifact_root).expanduser()
        self.result_root = Path(self.result_root).expanduser()


CONFIG = PipelineConfig()
