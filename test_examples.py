from src.agent import solve


def test_extraction():
    from src.utils import extract_code_blocks, has_final_answer

    text1 = "Let me solve this.\n```python\nfrom sympy import Symbol, diff\nx = Symbol('x')\nresult = diff(x**3, x)\nprint(result)\n```\nFinal Answer: 3x^2"
    assert extract_code_blocks(text1) == [
        "from sympy import Symbol, diff\nx = Symbol('x')\nresult = diff(x**3, x)\nprint(result)"
    ]
    assert has_final_answer(text1) == True

    text2 = "No code here."
    assert extract_code_blocks(text2) == []
    assert has_final_answer(text2) == False

    text3 = "最终答案是：42"
    assert has_final_answer(text3) == True

    print("All utility tests passed!")


def test_executor():
    from src.tools.executor import execute_code

    result = execute_code("from sympy import Symbol, diff\nx = Symbol('x')\nprint(diff(x**3, x))")
    assert result["success"] == True
    assert "3*x**2" in result["output"]
    print(f"SymPy test passed! Output: {result['output']}")

    result2 = execute_code("from scipy.stats import norm\nprint(norm.cdf(12, 10, 2))")
    assert result2["success"] == True
    print(f"scipy test passed! Output: {result2['output']}")

    result3 = execute_code("while True: pass")
    assert result3["success"] == False
    print("Timeout test passed!")

    result4 = execute_code("print(1 + 1)")
    assert result4["success"] == True
    assert result4["output"] == "2"
    print(f"Basic math test passed! Output: {result4['output']}")


def test_parse_solution_steps():
    from src.utils import parse_solution_steps

    numbered = "Step 1: 计算 f'(x)\nStep 2: 代入 x=2\nStep 3: 得到结果 12"
    steps = parse_solution_steps(numbered)
    assert len(steps) == 3
    assert "f'(x)" in steps[0]
    print(f"Numbered steps test passed! Steps: {steps}")

    plain = "首先求导 f'(x) = 3x²\n然后代入 x=2\n得到 f'(2) = 12"
    steps2 = parse_solution_steps(plain)
    assert len(steps2) >= 1
    print(f"Plain text steps test passed! Steps: {steps2}")

    single = "f'(x) = 3x², f'(2) = 12"
    steps3 = parse_solution_steps(single)
    assert len(steps3) >= 1
    print(f"Single line test passed! Steps: {steps3}")


def test_parse_premise_json():
    from src.utils import parse_premise_json

    json_response = """```json
{"step_index": 3, "premises": [0, 1, 2], "explanations": {"0": "problem provides f(x)", "1": "Step 1 computed the derivative", "2": "Step 2 substituted x=2"}}
```"""
    result = parse_premise_json(json_response, 3)
    assert result["step_index"] == 3
    assert 0 in result["premises"]
    assert 1 in result["premises"]
    assert 2 in result["premises"]
    print(f"JSON premise test passed! Result: {result}")

    plain_response = "The premises for step 4 are step 0 (the problem) and step 2 (the substitution result)."
    result2 = parse_premise_json(plain_response, 4)
    assert 0 in result2["premises"]
    assert 4 not in result2["premises"]
    print(f"Plain text premise test passed! Result: {result2}")


def test_detect_accumulation_errors():
    from src.utils import detect_accumulation_errors

    premise_links = {
        1: {"step_index": 1, "premises": [0], "explanations": {}},
        2: {"step_index": 2, "premises": [0, 1], "explanations": {}},
        3: {"step_index": 3, "premises": [0, 2], "explanations": {}},
    }
    native_errors = {1: "CALCULATION_ERROR", 2: None, 3: None}
    accumulation = detect_accumulation_errors(premise_links, native_errors)
    assert 2 in accumulation
    assert accumulation[2]["root_cause"] == 1
    assert 3 in accumulation
    assert 2 in accumulation[3]["faulty_premises"]
    print(f"Accumulation error test passed! Result: {accumulation}")


def test_extract_native_errors():
    from src.utils import extract_native_errors

    grading = (
        "**Step 1** (premises: [0]): 计算导数\n- 判断: ✓\n- 错误类别: 无\n\n"
        "**Step 2** (premises: [0, 1]): 代入x=2\n- 判断: ✗\n- 错误类别: CALCULATION_ERROR\n\n"
        "**Step 3** (premises: [0, 2]): 得到结果\n- 判断: ✓\n- 错误类别: 无"
    )
    errors = extract_native_errors(grading)
    assert errors.get(1) is None
    assert errors.get(2) == "CALCULATION_ERROR"
    assert errors.get(3) is None
    print(f"Native error extraction test passed! Result: {errors}")


def test_format_steps_with_premises():
    from src.utils import format_steps_with_premises

    steps = ["计算导数 f'(x)=3x²", "代入 x=2"]
    links = {
        1: {"premises": [0], "explanations": {}},
        2: {"premises": [0, 1], "explanations": {}},
    }
    result = format_steps_with_premises(steps, links)
    assert "**Step 1**" in result
    assert "**Step 2**" in result
    assert "premises: [0, 1]" in result
    print(f"Format steps test passed! Result:\n{result}")


def test_build_review_prompt():
    from src.prompts import build_review_prompt

    prompt = build_review_prompt(
        problem="求 ∫x²eˣdx",
        standard_reference="$$\\boxed{(x²-2x+2)eˣ+C}$$",
        student_steps="**Step 1** (premises: [0]): ...",
        premise_links="Step 1 ← premises: [0]",
    )
    assert "求 ∫x²eˣdx" in prompt
    assert "CALCULATION_ERROR" in prompt
    assert "ACCUMULATION_ERROR" in prompt
    assert "Multiple valid paths" in prompt
    assert "Superficial ≠ Error" in prompt
    print("Review prompt build test passed!")


def test_solve_yields_event_sequence():
    """B2: solve() 是 generator，事件序列必须以 final 结尾，且至少包含 started / step_start / step_done / final。"""
    from unittest.mock import patch
    from src.agent import solve

    mock_response = "### Step 1\n求解过程\n$$\\boxed{42}$$\n最终答案：42"

    def fake_solver_chat(messages, **kwargs):
        return mock_response

    with patch("src.agent.solver_chat", side_effect=fake_solver_chat):
        events = list(solve("求 1+1 等于几？"))

    event_types = [e.get("event") for e in events]
    assert "started" in event_types, f"missing 'started' in {event_types}"
    assert "step_start" in event_types, f"missing 'step_start' in {event_types}"
    assert "step_done" in event_types, f"missing 'step_done' in {event_types}"
    assert events[-1].get("event") == "final", f"last event should be 'final', got {events[-1]}"
    assert "result" in events[-1], "final event should carry 'result' dict"
    assert events[-1]["result"]["final_answer"] == mock_response
    assert events[-1]["result"]["difficulty"] in ("easy", "medium", "hard")
    print(f"Solve yields {len(events)} events, types: {event_types}")


def test_solve_multi_path_early_exit():
    """B1: USC 多路径求解，前两路答案一致时 yield usc_agreement 且 final 早退。"""
    from unittest.mock import patch
    from src.agent import solve

    call_count = {"n": 0}

    def fake_solver_chat(messages, **kwargs):
        call_count["n"] += 1
        return "### Step 1\n\n求解\n$$\\boxed{0.8413}$$"

    with patch("src.agent.solver_chat", side_effect=fake_solver_chat):
        # 用 hard 难度题（包含"证明"关键词）触发 USC 多路径
        events = list(solve("证明不等式：对任意正数 x，ln(x) <= x-1", image_path=None))

    event_types = [e.get("event") for e in events]

    # B1 核心断言：必须触发 usc_agreement，第 3 路不跑
    usc_agreement_events = [e for e in events if e.get("event") == "usc_agreement"]
    assert len(usc_agreement_events) == 1, f"expected 1 usc_agreement, got {len(usc_agreement_events)}"
    assert usc_agreement_events[0]["skipped"] >= 1, "should have skipped at least 1 path"

    # usc_path_start 应该是 2（不是 3）
    usc_path_starts = [e for e in events if e.get("event") == "usc_path_start"]
    assert len(usc_path_starts) == 2, f"expected 2 usc_path_start, got {len(usc_path_starts)}"

    # 没有 usc_selecting 事件（因为提前达成一致）
    usc_selecting = [e for e in events if e.get("event") == "usc_selecting"]
    assert len(usc_selecting) == 0, f"should not yield usc_selecting, got {len(usc_selecting)}"

    # final result 标记 usc_early_exit
    assert events[-1].get("event") == "final"
    assert events[-1]["result"].get("usc_early_exit") is True

    # 路径数对应的 step_start 数量：每路径 1 个 LLM 推理
    step_starts = [e for e in events if e.get("event") == "step_start" and e.get("label") == "LLM 推理"]
    assert len(step_starts) == 2, f"expected 2 step_starts from solver, got {len(step_starts)}"

    print(f"USC early exit OK: {len(usc_path_starts)} paths ran, {usc_agreement_events[0]['skipped']} skipped, {call_count['n']} total LLM calls (incl. verification)")


def test_solve_drains_internally():
    """review() 内部调 solve(fast=True) 必须用 _drain 消费，不向上泄漏 step 事件。"""
    from unittest.mock import patch
    from src.agent import review, _drain

    # _drain 应该只返回 final 的 result
    def gen():
        yield {"event": "started", "difficulty": "easy"}
        yield {"event": "step_start", "i": 1, "n": 1, "label": "x"}
        yield {"event": "step_done", "i": 1, "content": "y"}
        yield {"event": "final", "result": {"final_answer": "42"}}

    final = _drain(gen())
    assert final == {"final_answer": "42"}
    print("_drain correctly extracts final result")


if __name__ == "__main__":
    test_extraction()
    test_executor()
    test_parse_solution_steps()
    test_parse_premise_json()
    test_detect_accumulation_errors()
    test_extract_native_errors()
    test_format_steps_with_premises()
    test_build_review_prompt()
    test_solve_yields_event_sequence()
    test_solve_multi_path_early_exit()
    test_solve_drains_internally()
    print("\n✅ All tests passed!")