import json
from typing import Generator, Dict, Any, List
from app.sandbox import ExecutionSandbox
from app.agents import LLMClient, CoderAgent, CriticAgent

class MultiAgentEngine:
    def __init__(self, max_iterations: int = 4):
        self.max_iterations = max_iterations
        self.sandbox = ExecutionSandbox()
        self.llm = LLMClient()
        self.coder = CoderAgent(self.llm)
        self.critic = CriticAgent(self.llm)

    def run_stream(self, goal: str) -> Generator[Dict[str, Any], None, None]:
        """
        Yields state update events at every step of the orchestration loop.
        Useful for terminal logging and SSE streaming to the web UI.
        """
        yield {"step": "init", "message": f"Starting multi-agent workflow for goal: '{goal}'"}

        iteration_history: List[Dict[str, str]] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            yield {"step": "iteration_start", "iteration": iteration}

            # 1. Coder generates code
            yield {"step": "coder_thinking", "message": "Coder Agent is analyzing the task..."}
            try:
                coder_decision = self.coder.generate_code(goal, iteration_history)
            except Exception as e:
                yield {"step": "error", "message": f"Coder failed to generate JSON: {str(e)}"}
                break

            thought = coder_decision.get("thought", "")
            code = coder_decision.get("code", "")
            yield {
                "step": "coder_output",
                "thought": thought,
                "code": code
            }

            # 2. Execution Sandbox runs code
            yield {"step": "sandbox_executing", "message": "Executing code in isolated subprocess..."}
            exit_code, stdout, stderr = self.sandbox.run_python_code(code)
            yield {
                "step": "sandbox_output",
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr
            }

            # 3. Critic Agent evaluates output
            yield {"step": "critic_thinking", "message": "Critic Agent is reviewing the results..."}
            try:
                critique_res = self.critic.evaluate(goal, code, stdout, stderr, exit_code)
            except Exception as e:
                yield {"step": "error", "message": f"Critic evaluation failed: {str(e)}"}
                break

            approved = critique_res.get("approved", False)
            critique = critique_res.get("critique", "")
            final_answer = critique_res.get("final_answer", "")

            yield {
                "step": "critic_output",
                "approved": approved,
                "critique": critique,
                "final_answer": final_answer
            }

            if approved:
                yield {
                    "step": "completed",
                    "iterations": iteration,
                    "final_answer": final_answer
                }
                return

            # Feed the critique back to the coder for self-healing
            feedback_msg = (
                f"Iteration {iteration} Feedback:\n"
                f"Code:\n{code}\n"
                f"Stdout: {stdout}\nStderr: {stderr} (Exit: {exit_code})\n"
                f"Critic Feedback: {critique}\nPlease fix the issues and write revised code."
            )
            iteration_history.append({"role": "user", "content": feedback_msg})

        yield {
            "step": "failed",
            "message": f"Agent reached maximum iterations ({self.max_iterations}) without final approval."
        }
