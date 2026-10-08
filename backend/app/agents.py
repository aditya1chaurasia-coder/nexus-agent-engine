import json
import requests
import time
import logging
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    """Dispatches chat completions to either Ollama or OpenAI-compatible cloud endpoints."""
    def __init__(self):
        self.provider = settings.provider

    def chat(self, messages: List[Dict[str, str]], json_mode: bool = True, max_retries: int = 4, base_delay: float = 2.0) -> str:
        if self.provider == "ollama":
            url = f"{settings.ollama_url.rstrip('/')}/api/chat"
            payload = {
                "model": settings.ollama_model,
                "messages": messages,
                "stream": False
            }
            if json_mode:
                payload["format"] = "json"
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        else:
            base = settings.cloud_url.rstrip("/")
            endpoint = f"{base}/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.cloud_key.strip()}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings.cloud_model,
                "messages": messages
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            for attempt in range(max_retries):
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]

                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        retry_after = resp.headers.get("Retry-After")
                        try:
                            sleep_time = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                        except (ValueError, TypeError):
                            sleep_time = base_delay * (2 ** attempt)

                        logger.warning(f"HTTP {resp.status_code} hit. Backing off for {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(sleep_time)
                        continue

                raise RuntimeError(f"HTTP {resp.status_code} from {endpoint}: {resp.text}")

CODER_SYSTEM_PROMPT = """You are an expert Python Engineer Agent.
Your task is to write clean, complete, executable Python code to solve the user's objective.

Rules:
1. Always respond in valid JSON with these keys:
   {
     "thought": "<concise reasoning about how to approach or fix the problem>",
     "code": "<raw, complete python code to execute that prints results to stdout>"
   }
2. Ensure your code prints all output clearly to standard output.
3. If previous execution failed, analyze the error feedback and fix it.
4. STRICT EXECUTION RULES:
   - All code executes directly via python -c with NO command-line arguments.
   - NEVER use `sys.argv` or expect external inputs.
   - Do NOT import missing user files or modules. Embed all mocks, classes, tests, or demo data directly in the script.
   - Ensure syntactically valid Python without stray brackets.
"""

CRITIC_SYSTEM_PROMPT = """You are a Principal Software Architect and QA Critic.
Your role is to inspect the user's goal, the executed code, and its stdout/stderr feedback.

Rules:
1. Determine if the goal has been fully and correctly achieved.
2. Always respond in valid JSON with these keys:
   {
     "approved": true/false,
     "critique": "<concise feedback on what failed or needs fixing; empty if approved>",
     "final_answer": "<clear, comprehensive final explanation if approved; empty if not approved>"
   }
"""

class CoderAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate_code(self, goal: str, iteration_history: List[Dict[str, str]]) -> Dict[str, Any]:
        messages = [{"role": "system", "content": CODER_SYSTEM_PROMPT}]
        messages.append({"role": "user", "content": f"User Goal: {goal}"})
        messages.extend(iteration_history)
        raw = self.llm.chat(messages, json_mode=True)
        return json.loads(raw)

class CriticAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate(self, goal: str, code: str, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        trimmed_code = code[:2000] + "\n# ...[code trimmed for length]" if len(code) > 2000 else code
        trimmed_stdout = stdout[:1000] + "\n...[stdout trimmed]" if len(stdout) > 1000 else stdout
        trimmed_stderr = stderr[:1000] + "\n...[stderr trimmed]" if len(stderr) > 1000 else stderr

        prompt = (
            f"User Goal: {goal}\n\n"
            f"Executed Code:\n{trimmed_code}\n\n"
            f"Execution Exit Code: {exit_code}\n"
            f"Stdout:\n{trimmed_stdout}\n"
            f"Stderr:\n{trimmed_stderr}\n\n"
            f"Evaluate if this solves the user goal cleanly and without errors."
        )
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        raw = self.llm.chat(messages, json_mode=True)
        return json.loads(raw)
