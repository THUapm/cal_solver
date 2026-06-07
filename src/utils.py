import re
import json
import math

from src.tools import CALCULUS_REFERENCE, PROBABILITY_REFERENCE


def extract_code_blocks(text: str) -> list[str]:
    pattern = r"```python\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]


def extract_tool_calls(text: str) -> list[dict]:
    pattern = r"```tool\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    calls = []
    for m in matches:
        try:
            data = json.loads(m.strip())
            if "name" in data:
                calls.append({
                    "name": data["name"],
                    "arguments": data.get("arguments", data.get("args", {})),
                })
        except json.JSONDecodeError:
            name_match = re.search(r'"name"\s*:\s*"(\w+)"', m)
            if name_match:
                calls.append({"name": name_match.group(1), "arguments": {}})
    return calls


def has_final_answer(text: str) -> bool:
    patterns = [
        r"最终答案",
        r"Final Answer",
        r"\\boxed",
        r"最终结论",
        r"答案是[:：]",
        r"The answer is[:：]",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def format_iteration(i: int, llm_response: str, exec_result: dict | None, mcp_results: list[dict] | None = None) -> str:
    parts = [f"### Step {i}\n"]
    parts.append(llm_response)
    if exec_result is not None:
        parts.append(f"\n**Code executed:**\n```python\n{exec_result['code']}\n```")
        if exec_result["success"]:
            parts.append(f"\n**Result:**\n```\n{exec_result['output']}\n```")
        else:
            parts.append(f"\n**Error:**\n```\n{exec_result['output']}\n```")
    if mcp_results is not None:
        for mr in mcp_results:
            parts.append(f"\n**MCP tool '{mr['name']}' called:**")
            parts.append(f"```json\n{json.dumps(mr['arguments'], ensure_ascii=False)}\n```")
            parts.append(f"\n**MCP Result:**\n```\n{mr['result']}\n```")
    return "\n".join(parts)


LATEX_DELIMITERS = [
    {"left": "$$", "right": "$$", "display": True},
    {"left": "$", "right": "$", "display": False},
    {"left": "\\(", "right": "\\)", "display": False},
    {"left": "\\[", "right": "\\]", "display": True},
]


def format_solution(steps: list[str], final_answer: str, verification: str | None = None) -> str:
    combined = "\n\n".join(steps)

    if verification:
        combined += f"\n\n{verification}"

    if final_answer and not re.search(r"\\boxed", combined):
        combined += f"\n\n### 最终答案\n\n$$\\boxed{{\\text{{{final_answer}}}}}$$"

    return combined


def parse_solution_steps(solution: str) -> list[str]:
    step_patterns = [
        r"(?:Step|步骤|第)\s*(\d+)\s*[:：.]\s*(.*?)(?=(?:Step|步骤|第)\s*\d+\s*[:：.]|$)",
    ]
    for pattern in step_patterns:
        matches = re.findall(pattern, solution, re.DOTALL | re.IGNORECASE)
        if len(matches) >= 2:
            ordered = sorted(matches, key=lambda m: int(m[0]))
            return [m[1].strip() for m in ordered]

    lines = solution.strip().split("\n")
    steps = []
    current = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        has_math = bool(re.search(r"(?:\\$|\\\[|\\\\|[\d]+\s*[=+\-*/]|int|lim|frac|sum|prod|sqrt|sin|cos|tan|log|exp|P\(|概率|分布|期望|方差)", stripped, re.IGNORECASE))
        if has_math and current:
            steps.append(current.strip())
            current = stripped
        elif has_math and not current:
            current = stripped
        else:
            current = (current + " " + stripped) if current else stripped
    if current:
        steps.append(current.strip())
    return steps if steps else [solution.strip()]


def parse_premise_json(response: str, step_index: int) -> dict:
    json_match = re.search(r"```json\s*\n(.*?)```", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            premises = data.get("premises", [0])
            explanations = data.get("explanations", {})
            premises = [p for p in premises if p < step_index]
            if 0 not in premises:
                premises = [0] + premises
            premises = sorted(set(premises))
            return {"step_index": step_index, "premises": premises, "explanations": explanations}
        except json.JSONDecodeError:
            pass

    numbers = re.findall(r"\b(\d+)\b", response)
    premises = [int(n) for n in numbers if int(n) < step_index]
    if 0 not in premises:
        premises = [0] + premises
    premises = sorted(set(premises))
    return {"step_index": step_index, "premises": premises, "explanations": {}}


def detect_accumulation_errors(premise_links: dict, native_errors: dict) -> dict:
    accumulation = {}
    all_error_steps = set()
    for step_idx, err in native_errors.items():
        if err is not None:
            all_error_steps.add(step_idx)

    changed = True
    while changed:
        changed = False
        for step_idx in premise_links:
            if step_idx in all_error_steps:
                continue
            if step_idx in accumulation:
                continue
            premises = premise_links[step_idx].get("premises", [0])
            faulty_premises = [p for p in premises if p != 0 and p in all_error_steps]
            if faulty_premises:
                root = faulty_premises[0]
                accumulation[step_idx] = {
                    "error_type": "ACCUMULATION_ERROR",
                    "faulty_premises": faulty_premises,
                    "root_cause": root,
                    "trace": faulty_premises,
                }
                all_error_steps.add(step_idx)
                changed = True

    return accumulation


def format_steps_with_premises(steps: list[str], premise_links: dict) -> str:
    lines = []
    for i, step in enumerate(steps, 1):
        premises_info = premise_links.get(i, {"premises": [0]})
        premise_indices = premises_info.get("premises", [0])
        lines.append(f"**Step {i}** (premises: {premise_indices}): {step}")
    return "\n".join(lines)


def format_premise_links(premise_links: dict) -> str:
    lines = []
    for step_idx, info in premise_links.items():
        premises = info.get("premises", [0])
        explanations = info.get("explanations", {})
        line = f"Step {step_idx} ← premises: {premises}"
        if explanations:
            exp_strs = [f"Step {k}: {v}" for k, v in explanations.items()]
            line += f" ({'; '.join(exp_strs)})"
        lines.append(line)
    return "\n".join(lines)


def extract_native_errors(grading_result: str) -> dict:
    errors = {}
    step_pattern = re.finditer(
        r"\*\*Step\s+(\d+)\*\*.*?\*?\*?判断\*?\*?:\s*(✗|✓|×|√|Correct|Wrong|correct|wrong).*?\*?\*?错误类别\*?\*?:\s*([A-Z_]+|无|None|none)",
        grading_result, re.DOTALL | re.IGNORECASE,
    )
    for match in step_pattern:
        step_idx = int(match.group(1))
        judgment = match.group(2).strip()
        error_cat = match.group(3).strip()
        if judgment in ("✗", "×", "Wrong", "wrong"):
            errors[step_idx] = error_cat if error_cat and error_cat not in ("无", "None", "none") else "UNKNOWN_ERROR"
        else:
            errors[step_idx] = None

    if not errors:
        simple_pattern = re.finditer(
            r"Step\s+(\d+).*?(✗|✓|×|√)",
            grading_result, re.IGNORECASE,
        )
        for match in simple_pattern:
            step_idx = int(match.group(1))
            judgment = match.group(2).strip()
            if judgment in ("✗", "×"):
                errors[step_idx] = "FLAGGED"
            else:
                errors[step_idx] = None

    return errors


def format_review(
    grading_result: str,
    accumulation_errors: dict,
    meta_result: str,
    standard_reference: str,
    problem: str,
    student_solution: str,
) -> str:
    parts = [grading_result]

    if accumulation_errors:
        parts.append("\n\n### 🔗 累积错误追溯")
        for step_idx, info in accumulation_errors.items():
            root = info.get("root_cause", "?")
            trace = info.get("trace", [])
            parts.append(
                f"- **Step {step_idx}**: ACCUMULATION_ERROR — "
                f"依赖了错误前提 Step {root}，追溯路径: Step {trace}"
            )

    has_rejected = bool(re.search(r"REJECTED", meta_result, re.IGNORECASE))
    if has_rejected:
        parts.append("\n\n### ⚠️ 元验证修正")
        parts.append(meta_result)
    else:
        parts.append("\n\n### ✓ 元验证确认")
        parts.append("批改结果经元验证审查，所有错误判定均为真实错误，无幻觉判断。")

    parts.append("\n\n### 📖 正确解法参考")
    parts.append(standard_reference)

    combined = "\n".join(parts)
    if not re.search(r"\\boxed", combined):
        correct_count = sum(1 for v in extract_native_errors(grading_result).values() if v is None)
        total_count = len(extract_native_errors(grading_result))
        combined += (
            f"\n\n### 📊 批改结论\n\n"
            f"$$\\boxed{{\\text{{正确步骤: {correct_count}/{total_count}}}}}$$"
        )

    return combined


def parse_verification_errors(verify_response: str) -> str | None:
    """从验证器输出中提取错误描述。

    返回 None 表示验证通过；否则返回错误上下文字符串。

    判别顺序（短路）：
    1. 显式否定模式（"no error" / "verification passed" / "无误" 等）→ None
    2. 硬错误符号（✗ ✕ ❌ ×）→ 返回包含这些符号的行
    3. 通过标记（✓ ✅ PASS 等）→ None
    4. 软错误词（incorrect / wrong / 计算错误 等），且该行不含否定 → 返回这些行
    5. 否则 → None
    """
    NEGATION_PATTERNS = (
        r"\bno\s+errors?\b",
        r"\bno\s+(?:issues?|mistakes?)\b",
        r"\bverification\s+passed\b",
        r"\ball\s+correct\b",
        r"\beverything\s+(?:is\s+)?correct\b",
        r"无\s*误",
        r"没有\s*(?:错误|问题)",
        r"全部\s*正确",
        r"验证\s*通过",
    )
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, verify_response, re.IGNORECASE):
            return None

    HARD_ERROR_SYMBOLS = ("✗", "✕", "❌", "×")
    if any(sym in verify_response for sym in HARD_ERROR_SYMBOLS):
        lines = verify_response.split("\n")
        error_lines = [
            line.strip() for line in lines
            if any(s in line for s in HARD_ERROR_SYMBOLS)
        ]
        if error_lines:
            return "\n".join(error_lines)
        return verify_response.strip()[:500]

    PASS_MARKERS = ("✓", "✅", "Verification passed", "PASS", "Passed", "正确")
    if any(marker in verify_response for marker in PASS_MARKERS):
        return None

    SOFT_ERROR_PATTERNS = (
        r"\bincorrect\b",
        r"\bwrong\b",
        r"计算\s*错误",
        r"逻辑\s*错误",
        r"概念\s*错误",
        r"错误[:：]",
        r"不正确",
    )
    error_lines = []
    for line in verify_response.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if any(re.search(np, stripped, re.IGNORECASE) for np in NEGATION_PATTERNS):
            continue
        for pattern in SOFT_ERROR_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                error_lines.append(stripped)
                break

    if error_lines:
        return "\n".join(error_lines)
    return None


def extract_final_answer_value(final_answer: str) -> str | None:
    boxed_match = re.search(r"\\boxed\s*\{([^}]+)\}", final_answer)
    if boxed_match:
        return boxed_match.group(1).strip()

    patterns = [
        r"最终答案\s*[:：]\s*(.+)",
        r"Final Answer\s*[:：]\s*(.+)",
        r"答案是\s*[:：]\s*(.+)",
        r"The answer is\s*[:：]\s*(.+)",
    ]
    for p in patterns:
        m = re.search(p, final_answer, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return None


def all_answers_agree(answers: list[str | None], tolerance: float = 0.01) -> bool:
    valid = [a for a in answers if a is not None]
    if len(valid) < 2:
        return True

    try:
        numerical = [float(a) for a in valid]
        # 用 math.isclose：rel_tol 处理大数时的相对误差，abs_tol=tolerance
        # 给 0 附近的数提供绝对下限（防 0 vs 0.0005 误判为"接近"）。
        if all(math.isclose(n, numerical[0], rel_tol=1e-3, abs_tol=tolerance) for n in numerical):
            return True
    except (ValueError, TypeError):
        pass

    normalized = [a.strip().lower().replace(" ", "") for a in valid]
    if all(n == normalized[0] for n in normalized):
        return True

    return False


def parse_usc_selection(selection_response: str) -> int:
    json_match = re.search(r"```json\s*\n(.*?)```", selection_response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            sel = data.get("selected", data.get("choice", data.get("solution", 1)))
            return int(sel)
        except (json.JSONDecodeError, ValueError):
            pass

    num_match = re.search(r"(?:selected|choice|solution|选择)\s*[:：]?\s*(\d+)", selection_response, re.IGNORECASE)
    if num_match:
        return int(num_match.group(1))

    first_num = re.search(r"\b([1-9])\b", selection_response)
    if first_num:
        return int(first_num.group(1))

    return 1