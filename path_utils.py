"""Consistent input, artifact, and result paths for each run."""
from __future__ import annotations

import re
from pathlib import Path

from config import PipelineConfig


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._") or "item"


def model_output_root(root: Path, cfg: PipelineConfig) -> Path:
    folder = root / safe_name(cfg.llm.agent) / safe_name(cfg.llm.model)
    if cfg.run_name:
        folder /= safe_name(cfg.run_name)
    return folder


def run_root(cfg: PipelineConfig) -> Path:
    return model_output_root(cfg.artifact_root, cfg) / safe_name(cfg.dataset.name)


def artifact_path(cfg: PipelineConfig, category: str, task_id: str, filename: str) -> Path:
    folder = run_root(cfg) / category / safe_name(task_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def local_original_path(cfg: PipelineConfig, task_id: str) -> Path:
    return cfg.data_root / "original_code" / safe_name(cfg.dataset.name) / f"{safe_name(task_id)}.py"


def save_original_code(cfg: PipelineConfig, task_id: str, code: str) -> Path:
    """Materialize benchmark source in data/original_code for inspection/reuse."""
    path = local_original_path(cfg, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(code, encoding="utf-8")
    temporary_path.replace(path)
    return path


def result_csv_path(cfg: PipelineConfig) -> Path:
    folder = model_output_root(cfg.result_root, cfg) / safe_name(cfg.dataset.name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "behavior_assessment.csv"
