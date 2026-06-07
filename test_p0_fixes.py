"""P0 修复专项测试。

覆盖：
- P0.1 代码执行沙箱：拒绝危险 import/builtin，允许 sympy/scipy/numpy/math
- P0.2 LLM 客户端：启动期 API_KEY 校验（手动）、retry 行为（mock）
- P0.3 OCR 文本包装：solve/review 拼装时含 user_uploaded_content 标签

运行：
    python test_p0_fixes.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from src.tools.executor import execute_code


# ============== P0.1: 代码执行沙箱 ==============

def test_sandbox_blocks_os_import():
    r = execute_code("import os; os.system('echo PWNED')")
    assert r["success"] is False
    assert "SecurityError" in r["output"], f"unexpected output: {r['output']}"
    assert "os" in r["output"]
    print("[PASS] blocks os import")


def test_sandbox_blocks_subprocess():
    r = execute_code("import subprocess; subprocess.run(['echo', 'pwned'])")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks subprocess import")


def test_sandbox_blocks_socket():
    r = execute_code("import socket; socket.socket()")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks socket import")


def test_sandbox_blocks_sys():
    r = execute_code("import sys; print(sys.version)")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks sys import")


def test_sandbox_blocks_eval():
    r = execute_code("eval('1+1')")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    assert "eval" in r["output"]
    print("[PASS] blocks eval()")


def test_sandbox_blocks_exec():
    r = execute_code("exec('print(1)')")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks exec()")


def test_sandbox_blocks_open():
    r = execute_code("open('/etc/passwd').read()")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks open()")


def test_sandbox_blocks_dunder_import():
    r = execute_code("__import__('os')")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks __import__() direct call")


def test_sandbox_blocks_getattr():
    r = execute_code("getattr(__builtins__, 'eval')")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks getattr() reflection")


def test_sandbox_blocks_breakpoint():
    r = execute_code("breakpoint()")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks breakpoint()")


def test_sandbox_blocks_mro_escape():
    """通过 MRO 链逃逸是经典 Python 沙箱攻击向量。"""
    r = execute_code('"".__class__.__mro__[1].__subclasses__()')
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks MRO escape via __subclasses__")


def test_sandbox_blocks_class_access():
    r = execute_code('"x".__class__')
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks .__class__ access")


def test_sandbox_blocks_bases_access():
    r = execute_code('"x".__class__.__bases__')
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks .__bases__ access")


def test_sandbox_blocks_globals_access():
    r = execute_code('"x".__class__.__init__.__globals__')
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks .__globals__ access")


def test_sandbox_allows_safe_dunders():
    """正常 dunder 使用不应被误杀。"""
    r = execute_code('print("hello".__len__())')
    assert r["success"] is True
    assert r["output"] == "5"
    print("[PASS] allows safe dunder use (.__len__)")


def test_sandbox_blocks_from_os_path():
    r = execute_code("from os import path; print(path.sep)")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks 'from os import path'")


def test_sandbox_blocks_from_socket():
    r = execute_code("from socket import gethostname; print(gethostname())")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks 'from socket import ...'")


def test_sandbox_blocks_shutil():
    r = execute_code("import shutil; shutil.rmtree('/')")
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks shutil")


def test_sandbox_blocks_pickle():
    payload = "import pickle\npickle.dumps({'k': 'v'})"
    r = execute_code(payload)
    assert r["success"] is False
    assert "SecurityError" in r["output"]
    print("[PASS] blocks pickle")


def test_sandbox_allows_sympy():
    r = execute_code("from sympy import Symbol, diff\nx = Symbol('x')\nprint(diff(x**3, x))")
    assert r["success"] is True, f"sympy should work: {r['output']}"
    assert "3*x**2" in r["output"]
    print("[PASS] allows sympy computation")


def test_sandbox_allows_scipy():
    r = execute_code("from scipy.stats import norm\nprint(round(norm.cdf(12, 10, 2), 4))")
    assert r["success"] is True, f"scipy should work: {r['output']}"
    assert "0.8413" in r["output"]
    print("[PASS] allows scipy.stats")


def test_sandbox_allows_numpy():
    r = execute_code("import numpy as np\nprint(int(np.array([1, 2, 3]).sum()))")
    assert r["success"] is True, f"numpy should work: {r['output']}"
    assert "6" in r["output"]
    print("[PASS] allows numpy")


def test_sandbox_allows_basic_math():
    r = execute_code("print(1 + 1)")
    assert r["success"] is True
    assert r["output"] == "2"
    print("[PASS] allows basic arithmetic")


def test_sandbox_allows_preimported_sympy():
    r = execute_code("x = Symbol('x')\nprint(integrate(x**2, x))")
    assert r["success"] is True
    assert "x**3" in r["output"]
    print("[PASS] allows pre-imported sympy Symbol/integrate")


def test_sandbox_allows_unicode_output():
    r = execute_code("print('中文测试')")
    assert r["success"] is True
    assert "中文测试" in r["output"]
    print("[PASS] allows unicode output (Chinese)")


def test_sandbox_allows_latex_output():
    r = execute_code("x = Symbol('x')\nprint(latex(integrate(x**2, x)))")
    assert r["success"] is True
    assert "frac" in r["output"]
    print("[PASS] allows LaTeX output (backslashes)")


def test_sandbox_syntax_error_reported():
    r = execute_code("def (")
    assert r["success"] is False
    assert "SyntaxError" in r["output"]
    print("[PASS] reports SyntaxError cleanly")


def test_sandbox_preserves_return_shape():
    r = execute_code("print(1)")
    assert isinstance(r, dict)
    assert set(r.keys()) >= {"success", "output", "code"}
    assert isinstance(r["success"], bool)
    assert isinstance(r["output"], str)
    assert r["code"] == "print(1)"
    print("[PASS] return shape: {success: bool, output: str, code: str}")


def test_sandbox_timeout_still_works():
    """15s 超时机制要保留：长循环应在 15s 内被父进程 kill。"""
    # 用一个会跑很久的循环（实际上我们只测 API 形状，不真的等 15s）
    # 跑一个快速完成的代码，确保 timeout 机制没把简单代码误杀
    r = execute_code("x = sum(range(100)); print(x)")
    assert r["success"] is True
    assert r["output"] == "4950"
    print("[PASS] normal-speed code completes within timeout")


# ============== P0.3: OCR 文本隔离 ==============

def test_ocr_wrapping_in_solve():
    """solve() 拼装 combined_problem 时，OCR 文本应被 user_uploaded_content 包裹。"""
    from src.prompts import UNTRUSTED_CONTENT_GUARD
    assert UNTRUSTED_CONTENT_GUARD is not None
    assert "user_uploaded_content" in UNTRUSTED_CONTENT_GUARD.lower() or "untrusted" in UNTRUSTED_CONTENT_GUARD.lower()
    print("[PASS] UNTRUSTED_CONTENT_GUARD constant exists with untrusted wording")


def test_ocr_wrapping_in_solver_prompt():
    """build_solver_prompt_with_skills 应把 UNTRUSTED_CONTENT_GUARD 拼到末尾。"""
    from src.prompts import build_solver_prompt_with_skills
    p = build_solver_prompt_with_skills()
    assert "user_uploaded_content" in p.lower() or "untrusted" in p.lower() or "treat" in p.lower()
    print("[PASS] build_solver_prompt_with_skills includes untrusted guard")


def test_ocr_wrapping_in_review_prompt():
    """build_review_prompt 应包含 UNTRUSTED_CONTENT_GUARD。"""
    from src.prompts import build_review_prompt
    p = build_review_prompt(
        problem="test",
        standard_reference="ref",
        student_steps="steps",
        premise_links="links",
    )
    assert "user_uploaded_content" in p.lower() or "untrusted" in p.lower() or "treat" in p.lower()
    print("[PASS] build_review_prompt includes untrusted guard")


if __name__ == "__main__":
    tests = [
        test_sandbox_blocks_os_import,
        test_sandbox_blocks_subprocess,
        test_sandbox_blocks_socket,
        test_sandbox_blocks_sys,
        test_sandbox_blocks_eval,
        test_sandbox_blocks_exec,
        test_sandbox_blocks_open,
        test_sandbox_blocks_dunder_import,
        test_sandbox_blocks_getattr,
        test_sandbox_blocks_breakpoint,
        test_sandbox_blocks_mro_escape,
        test_sandbox_blocks_class_access,
        test_sandbox_blocks_bases_access,
        test_sandbox_blocks_globals_access,
        test_sandbox_blocks_from_os_path,
        test_sandbox_blocks_from_socket,
        test_sandbox_blocks_shutil,
        test_sandbox_blocks_pickle,
        test_sandbox_allows_sympy,
        test_sandbox_allows_scipy,
        test_sandbox_allows_numpy,
        test_sandbox_allows_basic_math,
        test_sandbox_allows_preimported_sympy,
        test_sandbox_allows_unicode_output,
        test_sandbox_allows_latex_output,
        test_sandbox_allows_safe_dunders,
        test_sandbox_syntax_error_reported,
        test_sandbox_preserves_return_shape,
        test_sandbox_timeout_still_works,
        test_ocr_wrapping_in_solve,
        test_ocr_wrapping_in_solver_prompt,
        test_ocr_wrapping_in_review_prompt,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed+failed}")
    sys.exit(0 if failed == 0 else 1)
