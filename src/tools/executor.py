"""执行 LLM 生成的 Python 代码。

委托给子进程 src/tools/safe_runner.py，提供三层防御：
1. 子进程内 AST 静态扫描（safe_runner._static_security_check）
2. 子进程内 __builtins__ 受限白名单
3. 本文件 subprocess.run(..., timeout=TIMEOUT_SECONDS) 硬超时

返回形状向后兼容：{"success": bool, "output": str, "code": str}。
"""

import json
import logging
import os
import subprocess
import sys

TIMEOUT_SECONDS = 15
_SAFE_RUNNER_PATH = os.path.join(os.path.dirname(__file__), "safe_runner.py")
_RESULT_PREFIX = "__SANDBOX_RESULT__"


def execute_code(code: str) -> dict:
    """在受沙箱保护的子进程中执行 code，返回统一结果字典。"""
    # 强制子进程 stdout/stderr 用 UTF-8（Windows 默认 GBK 会在中文/LaTeX 输出时
    # 产生乱码或 surrogate，父进程读不出来）。PYTHONIOENCODING 是 Python 启动时
    # 读取的环境变量，比 sys.stdout.reconfigure() 在子进程内更可靠。
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            [sys.executable, _SAFE_RUNNER_PATH],
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logging.warning(f"sandbox subprocess timed out after {TIMEOUT_SECONDS}s")
        return {
            "success": False,
            "output": f"Execution timed out ({TIMEOUT_SECONDS}s)",
            "code": code,
        }
    except FileNotFoundError as e:
        logging.error(f"sandbox runner not found: {_SAFE_RUNNER_PATH}: {e}")
        return {
            "success": False,
            "output": f"SandboxUnavailable: {e}",
            "code": code,
        }

    stdout = result.stdout or ""
    parsed = _parse_sandbox_result(stdout)

    if parsed is not None:
        if result.returncode != 0 and not parsed.get("output"):
            parsed["output"] = (result.stderr or "").strip() or f"SandboxExitCode:{result.returncode}"
        return parsed

    # 兜底：runner 崩溃或输出格式异常
    err_text = (result.stderr or "").strip()
    if result.returncode != 0:
        return {
            "success": False,
            "output": err_text or f"SandboxExitCode:{result.returncode}",
            "code": code,
        }
    return {
        "success": True,
        "output": stdout.strip(),
        "code": code,
    }


def _parse_sandbox_result(stdout: str) -> dict | None:
    """从 safe_runner.py 的 stdout 解析 JSON 结果行。"""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith(_RESULT_PREFIX):
            continue
        payload = line[len(_RESULT_PREFIX):]
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return {
            "success": bool(data.get("success", False)),
            "output": str(data.get("output", "")),
            "code": str(data.get("code", "")),
        }
    return None
