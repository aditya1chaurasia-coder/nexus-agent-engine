import json
import requests
from typing import List, Dict, Any
from app.config import settings

class LLMClient:
    """Dispatches chat completions to either Ollama or OpenAI-compatible cloud endpoints."""
    def __init__(self):
        self.provider = settings.provider

    def chat(self, messages: List[Dict[str, str]], json_mode: bool = True) -> str:
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
            
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code} from {endpoint}: {resp.text}")
            return resp.json()["choices"][0]["message"]["content"]

CODER_SYSTEM_PROMPT = """You are an expert Python Engineer Agent.
Your task is to write clean, complete, executable Python code to solve the user's objective.

Rules:
1. Always respond in valid JSON with these keys:
   {
     "thought": "<reasoning about how to approach or fix the problem>",
     "code": "<raw, complete python code to execute that prints results to stdout>"
   }
2. Ensure your code prints all output clearly to standard output.
3. If previous execution failed, analyze the error feedback and fix it.
"""

CRITIC_SYSTEM_PROMPT = """You are a Principal Software Architect and QA Critic.
Your role is to inspect the user's goal, the executed code, and its stdout/stderr feedback.

Rules:
1. Determine if the goal has been fully and correctly achieved.
2. Always respond in valid JSON with these keys:
   {
     "approved": true/false,
     "critique": "<feedback on what failed or needs fixing; empty if approved>",
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
        prompt = (
            f"User Goal: {goal}\n\n"
            f"Executed Code:\n{code}\n\n"
            f"Execution Exit Code: {exit_code}\n"
            f"Stdout:\n{stdout}\n"
            f"Stderr:\n{stderr}\n\n"
            f"Evaluate if this solves the user goal cleanly and without errors."
        )
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        raw = self.llm.chat(messages, json_mode=True)
        return json.loads(raw)
