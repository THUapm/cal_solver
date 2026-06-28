import re
import json
import math

from src.tools import CALCULUS_REFERENCE, PROBABILITY_REFERENCE


LATEX_DELIMITERS: list[dict] = [
    {"left": "$$", "right": "$$", "display": True},
    {"left": "$", "right": "$", "display": False},
    {"left": chr(92) + "[", "right": chr(92) + "]", "display": True},
    {"left": chr(92) + "(", "right": chr(92) + ")", "display": False},
]


def extract_code_blocks(text: str) -> list[str]:
    pattern = r"```python\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]


def normalize_latex_for_katex(text: str) -> str:
    """归一化 OCR / LLM 输出的 LaTeX, 让 KaTeX 能正确渲染。

    修复:
    1. LLM / OCR 经常把 \\\\frac 写成 \\\\\\\\frac (4 个反斜杠), 这是 markdown 字符串的二次转义
       在 KaTeX 里要看到 \frac 必须是单反斜杠
    2. OCR 把 Unicode ⇒ 识别为 \\\\Rightarrow, 但 LLM 有时输出 \\\\Rightarrow 时会多写一个 \
    3. \\\\therefore / \\\\to / \\\\cdot 等
    """
    if not text:
        return text

    out = text

    out = re.sub(r"\\\\([a-zA-Z]+)", r"\\\1", out)
    out = re.sub(r"\\\\([a-zA-Z]+)", r"\\\1", out)

    out = out.replace("\\\\", "\\")

    out = re.sub(r"\\{3,}([a-zA-Z]+)", r"\\\1", out)

    return out


def latex_to_html(text: str) -> str:
    """Convert Markdown text with LaTeX formulas to HTML with MathML.

    Pipeline (block-aware, placeholder-safe):
      1. Pre-escape any literal placeholder echoes in the source text so they
         cannot collide with newly-issued ones.
      2. Stash all math segments (block $$...$$, \\[...\\], inline \\(...\\),
         $...$) to placeholders of the form ``<mslot data-i="N"></mslot>``.
         Custom HTML elements survive gr.HTML JSON serialization, are not
         stripped by Gradio's sanitizer, are invisible to the user (empty
         content), and do not collide with LLM/OCR output text.
      3. Split the remaining text into blocks separated by blank lines, then
         classify each block (heading, ordered list, unordered list, paragraph).
      4. Restore MathML by replacing ``<mslot data-i="N"></mslot>`` placeholders.
    """
    if not text:
        return ""

    try:
        from latex2mathml import converter as _mathml
    except ImportError:
        _mathml = None

    def _render_math(latex: str, display: bool) -> str:
        if _mathml is None:
            return f'<code class="tex-fallback">${latex}$</code>'
        try:
            html = _mathml.convert(latex, display="block" if display else "inline")
            wrapper = "math-block" if display else "math-inline"
            return f'<span class="{wrapper}">{html}</span>'
        except Exception:
            return f'<code class="tex-fallback">${latex}$</code>'

    # 1. Pre-escape any literal placeholder echoes in the source text.
    out = re.sub(
        r'<mslot\s+data-i="(\d+)"\s*>\s*</mslot>',
        r'&lt;mslot data-i="\1"&gt;&lt;/mslot&gt;',
        text,
    )

    math_blocks: list[str] = []

    def _slot(idx: int) -> str:
        return f'<mslot data-i="{idx}"></mslot>'

    def _stash(latex: str, display: bool) -> str:
        idx = len(math_blocks)
        math_blocks.append(_render_math(latex.strip(), display=display))
        return _slot(idx)

    def _stash_display_re(m):
        return _stash(m.group(1), display=True)

    def _stash_inline_re(m):
        return _stash(m.group(1), display=False)

    def _parse_delim(s: str, open_seq: str, close_seq: str, display: bool) -> str:
        """Scan s for open_seq...close_seq pairs (depth-aware), replace with placeholders."""
        out_parts: list[str] = []
        last_end = 0
        i = 0
        open_len = len(open_seq)
        close_len = len(close_seq)
        while i < len(s):
            if s[i:i + open_len] == open_seq:
                start = i
                j = i + open_len
                depth = 1
                while j < len(s):
                    if s[j:j + open_len] == open_seq:
                        depth += 1
                        j += open_len
                    elif s[j:j + close_len] == close_seq:
                        depth -= 1
                        if depth == 0:
                            latex = s[i + open_len:j]
                            out_parts.append(s[last_end:start])
                            out_parts.append(_stash(latex, display=display))
                            last_end = j + close_len
                            i = last_end
                            break
                        j += close_len
                    else:
                        j += 1
                else:
                    out_parts.append(s[last_end:])
                    last_end = len(s)
                    i = len(s)
                    break
            else:
                i += 1
        if last_end < len(s):
            out_parts.append(s[last_end:])
        return "".join(out_parts)

    # 2. Order: long delimiters first to avoid $$ being eaten by $ regex.
    out = re.sub(r"\$\$([^$]+?)\$\$", _stash_display_re, out, flags=re.DOTALL)
    out = _parse_delim(out, "\\[", "\\]", display=True)
    out = _parse_delim(out, "\\(", "\\)", display=False)
    out = re.sub(r"\$([^$\n]+?)\$", _stash_inline_re, out)

    # 3. Block-aware markdown → HTML
    chunks = re.split(r"\n[ \t]*\n", out)
    html_blocks: list[str] = []

    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
    _OL_RE = re.compile(r"^(\d+)\.\s+(.+)$")
    _UL_RE = re.compile(r"^[-*]\s+(.+)$")
    _BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
    _CODE_RE = re.compile(r"`([^`]+?)`")
    _LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    _HR_RE = re.compile(r"^---+\s*$")

    def _inline(s: str) -> str:
        s = _BOLD_RE.sub(r"<strong>\1</strong>", s)
        s = _CODE_RE.sub(r"<code>\1</code>", s)
        s = _LINK_RE.sub(r'<a href="\2" target="_blank">\1</a>', s)
        return s

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.split("\n")

        if len(lines) == 1 and _HR_RE.match(lines[0]):
            html_blocks.append("<hr/>")
            continue

        if len(lines) == 1:
            m = _HEADING_RE.match(lines[0])
            if m:
                level = len(m.group(1))
                text_content = _inline(m.group(2).strip())
                html_blocks.append(f"<h{level}>{text_content}</h{level}>")
                continue

        if all(_OL_RE.match(ln) for ln in lines if ln.strip()):
            items = "".join(
                f"<li>{_inline(_OL_RE.match(ln).group(2))}</li>" for ln in lines if ln.strip()
            )
            html_blocks.append(f'<ol class="md-list">{items}</ol>')
            continue

        if all(_UL_RE.match(ln) for ln in lines if ln.strip()):
            items = "".join(
                f"<li>{_inline(_UL_RE.match(ln).group(1))}</li>" for ln in lines if ln.strip()
            )
            html_blocks.append(f'<ul class="md-list">{items}</ul>')
            continue

        para = "<br/>".join(_inline(ln) for ln in lines)
        html_blocks.append(f'<p class="md-para">{para}</p>')

    out = "".join(html_blocks)

    # 4. Restore MathML placeholders.
    for idx, math_html in enumerate(math_blocks):
        out = out.replace(_slot(idx), math_html)

    return out


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
    """只保留解答过程，exec_result / mcp_results 参数保留以保持向后兼容。"""
    parts = [f"### Step {i}\n"]
    parts.append(llm_response)
    return "\n".join(parts)


def strip_code_blocks(text: str) -> str:
    """移除 LLM 输出里的所有 '```...```' 代码块 + LLM 内部对话/元叙述。

    包括 ```python / ```json / ```tool``` 等任意语言标记的多行代码块,
    也处理孤立未配对的 ``` 标记。

    额外剥除 LLM 的内部元叙述, 避免泄露到 UI:
    - ### Step N 类编号
    - **Step N: ...** 类 LLM 复述编号 (KaTeX 会把 * 解析为上标导致整段乱码)
    - [步骤N] 类前缀
    - "输出:" / "实际上" / "我们还可以" / "注意:" 等 agent 间对话
    """
    cleaned = text

    # 1. 配对的代码块
    cleaned = re.sub(r"```[a-zA-Z]*\n.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)

    # 2. 孤立的代码块
    cleaned = re.sub(
        r"```[a-zA-Z]*[^\n]*\n(?:.*?\n)*?(?=\n\n|\n#|\Z)",
        "",
        cleaned,
    )

    # 3. 剥 ### Step N 类元编号
    cleaned = re.sub(r"###\s*Step\s*\d+\s*###?", "", cleaned, flags=re.IGNORECASE)

    # 3b. 剥 **Step N: ...** 类 LLM 复述编号 (KaTeX 会把 * 解析为上标导致整段乱码)
    # 用 [\s\S]*? 而不是 \s* (避免 ** 后接 \s* 零长度匹配问题)
    cleaned = re.sub(r"\*\*Step\s*\d+\s*[:：][\s\S]*?\*\*", "", cleaned, flags=re.IGNORECASE)

    # 4. 剥 [步骤N] / [Step N] 类前缀
    cleaned = re.sub(r"\[(?:步骤|Step)\s*\d+\]\s*[^\n]*\n?", "", cleaned, flags=re.IGNORECASE)

    # 5. 剥 LLM 内部 agent 对话 (句首/行首模式)
    agent_dialogue_patterns = [
        r"^\s*输出[：:].*?\n",
        r"^\s*输出[（(]简化.*?[)）]\s*[:：]?\s*\n?",
        r"^\s*实际上[，,].*?\n",
        r"^\s*我们还可以.*?\n",
        r"^\s*我们应.*?\n",
        r"^\s*现在用.*?验证.*?\n",
        r"^\s*注意[：:].*?\n",
    ]
    for pat in agent_dialogue_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.MULTILINE)

    # 6. 剥孤立的'输出' / 'Output' 单词
    cleaned = re.sub(r"^\s*输出\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*Output\s*$", "", cleaned, flags=re.MULTILINE | re.IGNORECASE)

    # 7. 全角 ∗ (U+2217) 与半角 * 互相还原（LLM 偶尔把 ** 写成 ∗∗ 导致 markdown bold 失效）
    cleaned = cleaned.replace("∗", "*")

    # 8. 中文双字去重：OCR 经常把"令"识别为"令令"、"代回"识别为"代回代回"
    # 仅当一个 2-4 字中文词被连续重复 ≥2 次时压缩为 1 次
    cleaned = re.sub(
        r"([\u4e00-\u9fff]{1,4}?)\1+",
        r"\1",
        cleaned,
    )

    # 9. 压缩连续空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _expand_equation_chains(text: str) -> str:
    """后处理: 把跨行 / 含求导符号的 $...$ 升级为 $$...$$ 块, 避免 KaTeX 渲染失败。

    KaTeX 在 $...$ 行内上下文里不支持 \\ (多行换行), 但在 $$...$$ 块里支持。
    LLM 经常把多行等式链 (如 "a = b \\ c = d") 或含求导符号 (h') 的公式写在 $...$ 内,
    渲染时上标会掉下一行 / 求导符号丢失。
    本函数检测含换行符 / 连续反斜杠 / 求导符号的 $...$ 区段, 升为 $$...$$ 独占块。
    """
    if not text:
        return text

    def _maybe_upgrade(m):
        inner = m.group(1)
        has_unicode_arrow = any(c in inner for c in chr(0x21D2) + chr(0x21D0) + chr(0x21D4) + chr(0x21D1) + chr(0x21D3) + chr(0x27F6) + chr(0x27F9) + chr(0x27F8))
        has_latex_arrow = bool(re.search(r"\\(?:Rightarrow|Leftarrow|Leftrightarrow|to|mapsto|longrightarrow|longmapsto)", inner))
        if "\n" in inner or "\'" in inner or has_unicode_arrow or has_latex_arrow or len(inner) > 60:
            return "$$\n" + inner.strip() + "\n$$"
        return m.group(0)

    return re.sub(r"\$([^$]+?)\$", _maybe_upgrade, text, flags=re.DOTALL)

def format_solution(steps: list[str], final_answer: str, verification: str | None = None) -> str:
    # 先对每步 strip_code_blocks (剥 **Step N:** / 内部对话), 再 join
    cleaned_steps = [strip_code_blocks(s) for s in steps]
    cleaned_steps = [s for s in cleaned_steps if s]  # 移除空步
    combined = "\n\n".join(cleaned_steps)

    if verification:
        combined += f"\n\n{verification}"

    if final_answer and not re.search(r"\\boxed", combined):
        combined += f"\n\n### 最终答案\n\n$$\\boxed{{\\text{{{final_answer}}}}}$$"

    return _expand_equation_chains(combined)

def parse_solution_steps(solution: str) -> list[str]:
    step_patterns = [
        r"(?:Step|步骤|第)\s*(\d+)\s*[:：.]\s*(.*?)(?=(?:Step|步骤|第)\s*\d+\s*[:：.]|$)",
    ]
    for pattern in step_patterns:
        matches = re.findall(pattern, solution, re.DOTALL | re.IGNORECASE)
        if len(matches) >= 2:
            ordered = sorted(matches, key=lambda m: int(m[0]))
            steps = [m[1].strip() for m in ordered]
            return _dedupe_steps_by_number(steps)

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
    return _dedupe_steps_by_number(steps) if steps else [solution.strip()]


def _dedupe_steps_by_number(steps: list[str]) -> list[str]:
    """去重 OCR/agent 重复识别产生的步骤。

    两种去重策略叠加:
    1. 显式编号去重: step 文本开头有 "Step N:" / "步骤N" / "第N步"，按 N 分组保留最长版本
    2. 内容相似度去重: 多个 step 内容高度相似（SequenceMatcher ratio > 0.7）只保留最长
    """
    from difflib import SequenceMatcher
    num_pat = re.compile(r"^\s*(?:Step|步骤|第)\s*(\d+)\s*[:：.]", re.IGNORECASE)

    by_num: dict[int, str] = {}
    others: list[str] = []
    for s in steps:
        m = num_pat.match(s)
        if m:
            n = int(m.group(1))
            if n not in by_num or len(s) > len(by_num[n]):
                by_num[n] = s
        else:
            others.append(s)

    if by_num:
        unique = [by_num[k] for k in sorted(by_num)]
    else:
        unique = list(steps)

    final: list[str] = []
    for s in unique + others:
        is_dup = False
        for kept in final:
            ratio = SequenceMatcher(None, s.strip(), kept.strip()).ratio()
            if ratio > 0.7 and len(s) <= len(kept) * 1.3:
                is_dup = True
                break
        if not is_dup:
            final.append(s)
    return final


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
    parts.append(strip_code_blocks(standard_reference))

    combined = "\n".join(parts)
    if not re.search(r"\\boxed", combined):
        correct_count = sum(1 for v in extract_native_errors(grading_result).values() if v is None)
        total_count = len(extract_native_errors(grading_result))
        combined += (
            f"\n\n### 📊 批改结论\n\n"
            f"$$\\boxed{{\\text{{正确步骤: {correct_count}/{total_count}}}}}$$"
        )

    return _expand_equation_chains(combined)


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

def parse_step_confidence(grading_text):
    """Parse confidence per step from grading result. Returns {step_num: confidence}."""
    if not grading_text:
        return {}

    block_pattern = re.compile(
        r'(?:\*\*)?(?:Step|步骤)\s*(\d+)(?:\*\*)?[\s:：.-]*'
        r'(.*?)(?=(?:\*\*)?(?:Step|步骤)\s*\d+(?:\*\*)?[\s:：.-]*|\Z)',
        re.I | re.S,
    )
    result = {}
    for step, body in block_pattern.findall(grading_text):
        m = re.search(r'置信度\*?\*?\s*[:：]?\s*(\d{1,3})\s*%?', body, re.S)
        if m:
            result[int(step)] = max(0, min(100, int(m.group(1))))

    if result:
        return result

    matches = re.findall(r'置信度\*?\*?\s*[:：]?\s*(\d{1,3})\s*%?', grading_text, re.S)
    return {i + 1: max(0, min(100, int(c))) for i, c in enumerate(matches)}


def parse_step_correctness(grading_text):
    """Parse correctness per step. Returns {step_num: is_correct}."""
    if not grading_text:
        return {}

    block_pattern = re.compile(
        r'(?:\*\*)?(?:Step|步骤)\s*(\d+)(?:\*\*)?[\s:：.-]*'
        r'(.*?)(?=(?:\*\*)?(?:Step|步骤)\s*\d+(?:\*\*)?[\s:：.-]*|\Z)',
        re.I | re.S,
    )
    result = {}
    for step, body in block_pattern.findall(grading_text):
        m = re.search(r'判断\*?\*?\s*[:：]?\s*([✓✗对错正确错误]|correct|incorrect|right|wrong)', body, re.I | re.S)
        if m:
            token = m.group(1).lower()
            result[int(step)] = token in {chr(0x2713), '对', '正确', 'correct', 'right'}

    if result:
        return result

    matches = re.findall(r'判断\*?\*?\s*[:：]?\s*([✓✗对错正确错误]|correct|incorrect|right|wrong)', grading_text, re.I | re.S)
    return {
        i + 1: c.lower() in {chr(0x2713), '对', '正确', 'correct', 'right'}
        for i, c in enumerate(matches)
    }


def classify_confidence_badge(confidence, is_correct):
    """Return badge class: correct-high / correct-med / error."""
    if not is_correct:
        return "error"
    if confidence >= 90:
        return "correct-high"
    if confidence >= 70:
        return "correct-med"
    return "error"


def parse_similar_problems(similar_text):
    """Parse similar problems list from generator output."""
    problems = []
    blocks = re.split(r'### 题目\s*(\d+)', similar_text)
    for i in range(1, len(blocks), 2):
        idx = blocks[i]
        body = blocks[i + 1].strip()
        m = re.search(r'\*\*答[::]?\*\*\s*[:：]?\s*(.+?)(?=###|$)', body, re.S)
        if m:
            answer = m.group(1).strip().rstrip('`').strip()
            problem = body[: m.start()].rstrip('**答**').strip()
        else:
            answer = ''
            problem = body
        problems.append({'index': int(idx), 'problem': problem, 'answer': answer})
    return problems
