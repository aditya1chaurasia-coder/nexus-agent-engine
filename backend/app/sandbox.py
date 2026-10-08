import os
import subprocess
import sys
from typing import Tuple

class ExecutionSandbox:
    @staticmethod
    def run_python_code(code: str, timeout: int = 15) -> Tuple[int, str, str]:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        try:
            res = subprocess.run(
                [sys.executable, '-c', code],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, '', f'Execution timed out after {timeout} seconds.'
        except Exception as exc:
            return -1, '', str(exc)
