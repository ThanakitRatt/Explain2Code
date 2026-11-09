"""Explanation-guided C -> E -> C' reconstruction using isolated sessions.

The generated-code session receives the explanation only, not the original
code. This preserves the reference pipeline's defining round-trip algorithm.
"""
from __future__ import annotations

import re

from config import CONFIG, PipelineConfig
from llm import LLMClient
from path_utils import artifact_path
from trace import Timer, Tracer


EXPLAIN_SYSTEM = (
    "You are an expert software engineer. Explain code precisely, including function names "
    "in natural language so another engineer could reimplement it without seeing the code."
)
GENERATE_SYSTEM = (
    "You are an expert Python developer. Implement code strictly from a natural "
    "language specification. Output only a single Python code block."
)
EXPLAIN_TEMPLATE = (
    # "Explain the following Python code in clear natural language. Describe its "
    # "purpose, inputs, outputs, and step-by-step logic. Do NOT include any code.\n\n"
    # "```python\n{code}\n```"
    
    "Explain the following Python code in clear natural language. Describe its "
    "purpose, inputs, outputs, and step-by-step logic. Retaining the algorithmic approach and variable type information. Do NOT include any code.\n\n"
    "```python\n{code}\n```"
)
GENERATE_TEMPLATE = (
    "Write a complete, self-contained Python implementation that satisfies the "
    "following natural-language specification.\n"
    "Output only Python code. Do not add alias functions or rename anything.\n\n"
    "Specification:\n{explanation}{name_clause}"
)


def extract_code_block(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


class Reconstruction:
    def __init__(self, client: LLMClient | None = None, cfg: PipelineConfig | None = None,
                 tracer: Tracer | None = None):
        self.cfg = cfg or CONFIG
        self.client = client or LLMClient(self.cfg.llm)
        self.tracer = tracer

    def explain(self, task_id: str, code: str) -> str:
        print(f"{task_id}: asking {self.cfg.llm.agent} to explain original code", flush=True)
        prompt = EXPLAIN_TEMPLATE.format(code=code)
        session = self.client.new_session(EXPLAIN_SYSTEM)
        try:
            with Timer() as timer:
                explanation = session.ask(prompt).strip()
        finally:
            session.kill()
        if self.tracer:
            self.tracer.step(task_id, "explain", prompt, explanation, timer.elapsed)
        artifact_path(self.cfg, "explanation", task_id, "explanation.txt").write_text(
            explanation, "utf-8"
        )
        return explanation

    def regenerate(self, task_id: str, explanation: str, entry_point: str = "") -> str:
        print(f"{task_id}: asking {self.cfg.llm.agent} to reconstruct from explanation", flush=True)
        if entry_point:
            name_clause = (
                f"\nThe primary function MUST be named exactly `{entry_point}` "
                "with the same signature. Do NOT rename it, wrap it, or add alias functions."
            )
        else:
            name_clause = (
                "\nPreserve the exact function name(s) and signature(s) implied by the description."
            )
        prompt = GENERATE_TEMPLATE.format(
            explanation=explanation, name_clause=name_clause
        )
        session = self.client.new_session(GENERATE_SYSTEM)
        try:
            with Timer() as timer:
                response = session.ask(prompt)
        finally:
            session.kill()
        new_code = extract_code_block(response)
        if self.tracer:
            self.tracer.step(task_id, "reconstruct", prompt, new_code, timer.elapsed)
        artifact_path(self.cfg, "reconstructed_code", task_id, "reconstructed.py").write_text(
            new_code, "utf-8"
        )
        return new_code

    def run(self, task_id: str, original_code: str, entry_point: str = "") -> dict:
        explanation = self.explain(task_id, original_code)
        reconstructed = self.regenerate(task_id, explanation, entry_point)
        return {"task_id": task_id, "explanation": explanation, "new_code": reconstructed}
