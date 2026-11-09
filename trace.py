"""Trace prompts, responses, and elapsed time for reconstruction stages."""
from __future__ import annotations

import time

from config import PipelineConfig
from path_utils import artifact_path


class Timer:
    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed = time.perf_counter() - self.started


class Tracer:
    def __init__(self, cfg: PipelineConfig, verbose: bool = True):
        self.cfg = cfg
        self.verbose = verbose

    def step(self, task_id: str, name: str, prompt: str, response: str, elapsed: float) -> None:
        if self.verbose:
            print(f"[{task_id}] {name}: {elapsed:.1f}s")
        artifact_path(self.cfg, "trace", task_id, f"{name}_prompt.txt").write_text(prompt, "utf-8")
        artifact_path(self.cfg, "trace", task_id, f"{name}_response.txt").write_text(response, "utf-8")
