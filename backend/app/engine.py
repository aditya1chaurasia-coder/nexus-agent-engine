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

            # 1. Coder generates code (send sliding window of history to avoid TPM limits)
            yield {"step": "coder_thinking", "message": "Coder Agent is analyzing the task..."}
            try:
                active_history = iteration_history[-2:] if len(iteration_history) > 2 else iteration_history
                coder_decision = self.coder.generate_code(goal, active_history)
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

            # Compact the feedback so token consumption stays low
            trimmed_stdout = stdout[-500:] if len(stdout) > 500 else stdout
            trimmed_stderr = stderr[-500:] if len(stderr) > 500 else stderr
            feedback_msg = (
                f"Iteration {iteration} Failed (Exit {exit_code}):\n"
                f"Stdout tail: {trimmed_stdout}\n"
                f"Stderr tail: {trimmed_stderr}\n"
                f"Critic instructions: {critique}\n"
                f"Fix these specific issues in your revised code."
            )
            iteration_history.append({"role": "user", "content": feedback_msg})

        yield {
            "step": "failed",
            "message": f"Agent reached maximum iterations ({self.max_iterations}) without final approval."
        }
