"""受限 Python 运行时（沙箱子进程入口）。

设计为双层防御，配合 executor.py 使用：
- Layer 1（静态）：AST 扫描拒绝危险 import / builtin / 反射调用
- Layer 2（运行时）：__builtins__ 替换为白名单子集；预先 import 安全模块
- Layer 3（兜底）：父进程 subprocess.run(timeout=15) 硬 kill

通信协议：父进程通过 stdin 传入 code 字符串，子进程把结果以
单行 JSON 写到 stdout，格式: {"success": bool, "output": str, "code": str}。
异常 / 调试信息走 stderr。
"""

import ast
import builtins
import json
import sys
import textwrap
import traceback
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout

# Windows 默认 stdout 编码是 GBK，与父进程 text=True 的 UTF-8 不一致会导致解码失败。
# 显式 reconfigure 到 UTF-8（safe_runner.py 在子进程内运行，独立于父进程）。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# 沙箱内递归深度上限。SymPy 展开/化简 复杂多项式时栈深易超 500。
# 设到 2000：足够覆盖绝大多数数学运算，又避免单次调用把进程栈打爆。
_SANDBOX_RECURSION_LIMIT = 2000


# 拒绝 import 的根模块
FORBIDDEN_IMPORT_ROOTS = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "urllib3",
    "http", "ftplib", "smtplib", "telnetlib", "asyncio", "multiprocessing",
    "threading", "ctypes", "cffi", "_ctypes", "pickle", "shelve", "ssl",
    "select", "pty", "fcntl", "termios", "resource", "pwd", "grp",
    "platform", "pathlib", "glob", "tempfile", "io", "code", "codeop",
    "importlib", "builtins", "_thread",
})

# 拒绝 import 的子模块（from X import Y 形式）
FORBIDDEN_IMPORT_NAMES = frozenset({
    "io", "os", "sys", "subprocess", "socket",
})

# 拒绝调用的 builtin
FORBIDDEN_BUILTINS = frozenset({
    "eval", "exec", "compile", "open", "__import__",
    "breakpoint", "input", "getattr", "setattr", "delattr",
    "globals", "locals", "vars", "dir",
})

# 拒绝的属性访问（属性名以 dunder 形式出现，用于阻断 Python 沙箱逃逸）
# 这些 dunder 是经典 MRO/class-hierarchy 攻击链的入口点
FORBIDDEN_DUNDER_ATTRS = frozenset({
    "__class__", "__bases__", "__mro__", "__subclasses__",
    "__globals__", "__code__", "__builtins__", "__import__",
    "__loader__", "__spec__", "__dict__",
    "__getattribute__", "__getattr__",
})


def _static_security_check(code: str) -> str | None:
    """返回 None 表示代码通过；返回字符串说明被拒绝的原因。"""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno}, col {e.offset})"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS or alias.name in FORBIDDEN_IMPORT_NAMES:
                    return f"SecurityError: import '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            root = node.module.split(".")[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                return f"SecurityError: 'from {node.module} import ...' is not allowed"
            for alias in node.names:
                if alias.name in FORBIDDEN_IMPORT_NAMES:
                    return f"SecurityError: 'from {node.module} import {alias.name}' is not allowed"
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_BUILTINS:
                return f"SecurityError: builtin '{func.id}()' is not allowed"
            # 拦截 getattr(__builtins__, 'eval') 类的反射
            if isinstance(func, ast.Name) and func.id == "getattr":
                return f"SecurityError: 'getattr()' is not allowed"
        elif isinstance(node, ast.Attribute):
            # 拦截高危 dunder 属性访问（MRO/class-hierarchy 逃逸链入口）
            if node.attr in FORBIDDEN_DUNDER_ATTRS:
                return f"SecurityError: attribute '.{node.attr}' is not allowed"
    return None


# 受限 builtin 白名单
# 注：故意不包含 `type`。`type()` 既可用作类型查询，也是经典沙箱逃逸链
# (`type(x).__bases__`) 的入口。dunder 在 AST 已拦截，但少一个入口仍是
# defense-in-depth，且数学 LLM 代码极少需要 type()。
_SAFE_BUILTIN_NAMES = (
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "hash", "hex", "id", "int",
    "isinstance", "issubclass", "iter", "len", "list", "map", "max",
    "min", "next", "object", "oct", "ord", "pow", "print", "property",
    "range", "repr", "reversed", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "zip",
)


def _make_safe_import(real_import):
    """返回一个白名单门控的 __import__ 替代品。

    `import X` 语句在字节码层会调用 __import__，所以即便我们在 AST 层
    拒绝 `__import__("os")` 形式的直接调用，import 语句本身仍需要可用。
    这层包装是第二道闸口：AST 拦截直接调用，runtime 拦截 import 语句。
    """

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name is None:
            return None
        root = name.split(".")[0]
        if root in FORBIDDEN_IMPORT_ROOTS or name in FORBIDDEN_IMPORT_NAMES:
            raise ImportError(
                f"ImportError: import of '{name}' is not allowed in sandbox"
            )
        return real_import(name, globals, locals, fromlist, level)

    return _safe_import


def _build_safe_globals() -> dict:
    """构造受限的 globals 字典。"""
    import math
    import numpy as np
    import sympy
    from sympy import (
        Symbol, symbols, var, diff, integrate, limit, series, solve, Eq,
        simplify, expand, factor, latex, oo, pi, E, sin, cos, tan, log,
        sqrt, exp, Rational, Derivative, Integral, Limit, Matrix,
    )
    from math import factorial, comb, perm
    from scipy.stats import norm, binom, poisson, expon, uniform, chi2, t, beta, gamma, geom, hypergeom
    from itertools import combinations, product, permutations
    from collections import Counter

    safe_builtins = {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES}
    safe_builtins["__import__"] = _make_safe_import(builtins.__import__)

    return {
        "__name__": "__sandbox__",
        "__doc__": None,
        "__builtins__": safe_builtins,
        # 常用数学模块
        "math": math,
        "sympy": sympy,
        "np": np,
        "numpy": np,
        # sympy 符号
        "Symbol": Symbol, "symbols": symbols, "var": var,
        "diff": diff, "integrate": integrate, "limit": limit, "series": series,
        "solve": solve, "Eq": Eq, "simplify": simplify, "expand": expand, "factor": factor,
        "latex": latex, "oo": oo, "pi": pi, "E": E,
        "sin": sin, "cos": cos, "tan": tan, "log": log, "sqrt": sqrt, "exp": exp,
        "Rational": Rational, "Derivative": Derivative, "Integral": Integral, "Limit": Limit,
        "Matrix": Matrix,
        # math 内置
        "factorial": factorial, "comb": comb, "perm": perm,
        # scipy.stats
        "norm": norm, "binom": binom, "poisson": poisson, "expon": expon,
        "uniform": uniform, "chi2": chi2, "t": t, "beta": beta, "gamma": gamma,
        "geom": geom, "hypergeom": hypergeom,
        # itertools / collections
        "combinations": combinations, "product": product, "permutations": permutations,
        "Counter": Counter,
    }


def _run_sandboxed(code: str) -> dict:
    """在受限 globals 中执行 code，捕获 stdout/stderr/异常。"""
    err = _static_security_check(code)
    if err:
        return {"success": False, "output": err, "code": code}

    sys.setrecursionlimit(_SANDBOX_RECURSION_LIMIT)
    safe_globals = _build_safe_globals()
    safe_locals: dict = {}

    stdout_buf = StringIO()
    stderr_buf = StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, safe_globals, safe_locals)
    except SystemExit as e:
        return {"success": False, "output": f"SystemExit: {e}", "code": code}
    except BaseException:
        return {
            "success": False,
            "output": (stderr_buf.getvalue() + traceback.format_exc()).strip(),
            "code": code,
        }

    stdout_text = stdout_buf.getvalue()
    stderr_text = stderr_buf.getvalue()
    if stderr_text and not stdout_text:
        return {"success": False, "output": stderr_text.strip(), "code": code}
    return {"success": True, "output": stdout_text.strip(), "code": code}


def main() -> None:
    raw = sys.stdin.read()
    try:
        result = _run_sandboxed(raw)
    except Exception as e:
        result = {
            "success": False,
            "output": f"SandboxInternalError: {type(e).__name__}: {e}",
            "code": raw,
        }
    sys.stdout.write("__SANDBOX_RESULT__" + json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
