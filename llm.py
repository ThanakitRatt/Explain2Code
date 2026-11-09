"""Thin coding-agent session adapters for Claude Code, Codex CLI, and Ollama."""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from config import LLMConfig


@dataclass
class LLMSession:
    client: "LLMClient"
    system_prompt: str
    history: list[dict[str, str]] = field(default_factory=list)
    alive: bool = True

    def ask(self, prompt: str) -> str:
        if not self.alive:
            raise RuntimeError("Cannot use a terminated model session.")
        self.history.append({"role": "user", "content": prompt})
        answer = self.client.complete(self.system_prompt, self.history)
        self.history.append({"role": "assistant", "content": answer})
        return answer

    def kill(self) -> None:
        self.history.clear()
        self.alive = False


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def new_session(self, system_prompt: str) -> LLMSession:
        return LLMSession(self, system_prompt)

    def complete(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        if self.cfg.provider == "mock":
            return self._mock(messages[-1]["content"])
        if self.cfg.provider == "claude_cli":
            prompt = self._flatten(system_prompt, messages)
            result = self._run_command(
                [self.cfg.binary, "--print", "--model", self.cfg.model],
                input=prompt,
            )
            return result.stdout.strip()
        if self.cfg.provider == "codex_cli":
            prompt = self._flatten(system_prompt, messages)
            with tempfile.TemporaryDirectory(prefix="codex-response-") as folder:
                output_path = Path(folder) / "last_message.txt"
                workdir = Path(__file__).resolve().parent
                self._run_command(
                    [self.cfg.binary, "exec", "--ephemeral", "--skip-git-repo-check",
                     "-s", "read-only", "-m", self.cfg.model, "-o", str(output_path),
                     "-C", str(workdir), prompt],
                    cwd=workdir,
                    stream_output=True,
                )
                return output_path.read_text(encoding="utf-8").strip()
        if self.cfg.provider == "ollama":
            payload = {
                "model": self.cfg.model,
                "messages": [{"role": "system", "content": system_prompt}, *messages],
                "temperature": self.cfg.temperature,
                "max_tokens": self.cfg.max_tokens,
                "stream": True,
            }
            request = urllib.request.Request(
                f"{self.cfg.base_url.rstrip('/')}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
                method="POST",
            )
            print(
                f"Waiting for Ollama response from {self.cfg.model} "
                f"(timeout: {self.cfg.timeout_sec}s)...",
                flush=True,
            )
            parts = []
            try:
                with urllib.request.urlopen(request, timeout=self.cfg.timeout_sec) as response:
                    for raw_line in response:
                        line = raw_line.decode("utf-8").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content") or choices[0].get("message", {}).get("content")
                            if content:
                                parts.append(content)
                                print(".", end="", flush=True)
            except TimeoutError as exc:
                raise TimeoutError(
                    f"Ollama did not respond within {self.cfg.timeout_sec}s. "
                    "Check that Ollama is running and the selected model is available."
                ) from exc
            print(" done", flush=True)
            return "".join(parts)
        raise ValueError(f"Unsupported provider: {self.cfg.provider!r}")

    def _run_command(self, command: list[str], input: str | None = None,
                     cwd: Path | None = None,
                     stream_output: bool = False) -> subprocess.CompletedProcess:
        if stream_output:
            return self._run_streaming_command(command, cwd)
        try:
            return subprocess.run(
                command,
                input=input,
                text=True,
                capture_output=True,
                timeout=self.cfg.timeout_sec,
                check=True,
                cwd=cwd or Path(__file__).resolve().parent,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Agent command timed out after {self.cfg.timeout_sec}s."
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(
                f"Agent command exited with status {exc.returncode}: {detail}"
            ) from exc

    def _run_streaming_command(
        self, command: list[str], cwd: Path | None
    ) -> subprocess.CompletedProcess:
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            cwd=cwd or Path(__file__).resolve().parent,
        )
        print(
            f"Codex CLI started (model: {self.cfg.model}; "
            f"timeout: {self.cfg.timeout_sec}s). Progress is shown below.",
            flush=True,
        )
        try:
            while True:
                remaining = self.cfg.timeout_sec - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError(
                        f"Codex CLI timed out after {self.cfg.timeout_sec}s."
                    )
                try:
                    return_code = process.wait(timeout=min(30, remaining))
                    break
                except subprocess.TimeoutExpired:
                    elapsed = int(time.monotonic() - started)
                    print(
                        f"Codex is still working ({elapsed}s elapsed)...",
                        flush=True,
                    )

            if return_code != 0:
                raise RuntimeError(
                    f"Codex CLI exited with status {return_code}; "
                    "see the streamed Codex CLI output above."
                )
            return subprocess.CompletedProcess(command, return_code)
        except (TimeoutError, KeyboardInterrupt, RuntimeError):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise

    @staticmethod
    def _flatten(system_prompt: str, messages: list[dict[str, str]]) -> str:
        return "\n\n".join(
            [f"[System]\n{system_prompt}"]
            + [f"[{item['role'].title()}]\n{item['content']}" for item in messages]
        )

    @staticmethod
    def _mock(prompt: str) -> str:
        if "Explain the following" in prompt:
            code = prompt.split("```python\n", 1)[-1].split("\n```", 1)[0]
            return f"Reproduce this implementation exactly:\n```python\n{code}\n```"
        return "```python\ndef solution(*args, **kwargs):\n    return None\n```"
