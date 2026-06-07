"""MathSolver - 微积分与概率论解题智能体

现代产品风 Gradio UI（Linear/Notion 系）。
- LinearLight / LinearDark 主题切换
- Inter / JetBrains Mono 字体
- KaTeX auto-render（CDN）
- 求解 / 批改双 Tab，每步 yield 进度事件
- Examples 卡片网格（gr.Dataset + CSS 覆盖）
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import gradio as gr

from src.agent import solve, review, get_mcp_router
from src.llm_client import vision_chat, encode_image_to_base64
from src.prompts import VISION_SYSTEM_PROMPT, SOLUTION_VISION_PROMPT
from src.utils import LATEX_DELIMITERS

ASSETS = Path(__file__).parent / "assets"
HEAD = (ASSETS / "head.html").read_text(encoding="utf-8")
CSS = (ASSETS / "style.css").read_text(encoding="utf-8")

from assets.theme import LinearLight

# ==========================================================================
# Examples
# ==========================================================================

SOLVE_EXAMPLES = [
    ["求 f(x) = x^2 * e^x 的不定积分", None],
    ["计算 lim(x->0) sin(x)/x 的极限", None],
    ["求 f(x) = ln(x) + x^3 在 x=1 处的导数", None],
    ["计算定积分 ∫(0 to 1) x^2 dx", None],
    ["求 f(x) = e^x * sin(x) 的二阶导数", None],
    ["一个正态分布 N(μ=10, σ=2)，求 P(X<=12)", None],
    ["抛硬币10次，恰好出现3次正面的概率是多少？", None],
    ["已知P(A)=0.3, P(B|A)=0.8, P(B)=0.5，求P(A|B)（贝叶斯定理）", None],
    ["泊松分布参数λ=3，求P(X=0)和P(X<=5)", None],
    ["一个袋子中有5红3白2黑球，不放回取3球，恰好1红1白1黑的概率", None],
]

REVIEW_EXAMPLES = [
    ["求 ∫x²eˣdx", None, "Step 1: 用幂函数积分法则直接积分\n$$\\int x^2 e^x dx = \\frac{x^2 e^x}{3} + C$$", None],
    ["求 f(x)=x³在x=2处的导数", None, "Step 1: 对f(x)=x³求导得f'(x)=3x²\nStep 2: 代入x=2，f'(2)=3×4=12", None],
    ["已知P(A)=0.3, P(B|A)=0.8, P(B)=0.5，求P(A|B)", None, "Step 1: 由贝叶斯公式 P(A|B)=P(A)P(B)/P(B)\nStep 2: P(A|B)=0.3×0.5/0.5=0.3", None],
]


# ==========================================================================
# Event → info 文案映射
# ==========================================================================

def _format_event_as_info(ev: dict) -> str:
    """把 agent.py yield 的事件转成单行 Markdown 提示。"""
    e = ev.get("event")
    if e == "started":
        diff = ev.get("difficulty", "?")
        schema = ev.get("schema") or "未匹配"
        return f"⏳ 准备求解...  | 难度: {diff} | Schema: {schema}"
    if e == "step_start":
        return f"⏳ Step {ev['i']}/{ev['n']}: {ev['label']}"
    if e == "step_done":
        return f"✓ Step {ev['i']} 完成"
    if e == "code_executing":
        return f"🔧 Step {ev['i']} 执行代码中..."
    if e == "code_done":
        ok = "✓" if ev.get("success") else "✗"
        out = (ev.get("output") or "").strip()[:60]
        return f"{ok} Step {ev['i']} 代码执行完毕 | 输出: {out}"
    if e == "mcp_calling":
        return f"🔌 Step {ev['i']} 调用 MCP 工具: {ev.get('tool', '?')}..."
    if e == "mcp_done":
        result = (ev.get("result") or "")[:60].replace("\n", " ")
        return f"✓ Step {ev['i']} MCP 完成 | {result}"
    if e == "verifying":
        return f"🔍 验证中 (try {ev.get('i', 1)})..."
    if e == "verify_passed":
        return "✅ 验证通过"
    if e == "verify_failed":
        return f"⚠️ 验证发现错误，纠错中..."
    if e == "correcting":
        return f"🔧 纠错中 (try {ev['i']})..."
    if e == "usc_path_start":
        return f"🧠 USC path {ev['i']}/{ev['n']} (temp={ev.get('temp', 0):.2f})"
    if e == "usc_agreement":
        return f"✅ USC 早退 (a={ev.get('a')}, b={ev.get('b')})，跳过 {ev.get('skipped', 0)} 路径"
    if e == "usc_selecting":
        return f"🧠 USC 选优中 (n={ev.get('n', 3)})..."
    if e == "ocr_running":
        return f"🖼 识别 {ev.get('source', '?')} 图片中..."
    if e == "ocr_done":
        return f"✓ {ev.get('source', '?')} 图片识别完毕"
    if e == "reference_ready":
        return f"📝 参考解已生成 | 难度: {ev.get('difficulty', '?')}"
    if e == "premise_extracting":
        return f"🔗 提取前提 {ev.get('step')}/{ev.get('n', '?')}..."
    if e == "grading_step":
        return f"✏️ 批改第 {ev.get('step')}/{ev.get('n', '?')} 步..."
    if e == "meta_checking":
        return f"🧐 元验证中（检查批改是否有幻觉）..."
    return f"· {e}"


# ==========================================================================
# UI 回调
# ==========================================================================

def run_solve(problem: str, image, progress=gr.Progress(track_tqdm=False)):
    """Generator: yield (solution_md, answer_md, info_md) 更新。

    Gradio 5.x/6.x 识别 generator 函数，会按 yield 顺序更新绑定的 output 组件。
    """
    image_path = image if image else None
    if not (problem and problem.strip()) and not image_path:
        yield ("<div class='empty-state'><div class='empty-state-icon'>∫</div>请输入题目或上传图片</div>", "", "")
        return

    progress(0, desc="准备求解...")
    accumulated_solution = ""
    final_result = None
    last_info = "⏳ 准备求解..."

    try:
        for ev in solve(problem, image_path=image_path):
            info_md = _format_event_as_info(ev)
            last_info = info_md
            e = ev.get("event")

            if e == "step_start":
                i = ev.get("i", 0)
                n = ev.get("n", 1)
                if isinstance(i, int) and isinstance(n, int) and n > 0:
                    progress(i / n, desc=f"Step {i}/{n}")
            elif e == "step_done":
                content = ev.get("content", "")
                if accumulated_solution:
                    accumulated_solution += "\n\n" + content
                else:
                    accumulated_solution = content
                yield (accumulated_solution, "", last_info)
                continue
            elif e == "final":
                final_result = ev["result"]
                break
            elif e == "mcp_done":
                # 累积 MCP 结果到 solution（仅在下一步 step_done 之前显示）
                pass
            else:
                pass

            yield (accumulated_solution, "", last_info)
    except Exception as ex:
        yield (f"<div class='info-banner error'>❌ 求解失败: {ex}</div>", "", last_info)
        return

    if final_result is None:
        yield (f"<div class='info-banner warning'>⚠️ 求解未产出结果</div>", "", last_info)
        return

    difficulty = final_result.get("difficulty", "medium")
    schema = final_result.get("schema") or "未匹配"
    final_info = (
        f"✅ 完成 | 难度: {difficulty} | Schema: {schema}"
    )
    formatted = final_result.get("formatted_solution") or ""
    final_answer = final_result.get("final_answer") or ""
    progress(1.0, desc="完成")
    yield (formatted, final_answer, final_info)


def _wrap_untrusted(text: str, source: str) -> str:
    return (
        f'<user_uploaded_content source="{source}" trust="untrusted">\n'
        f"{text}\n"
        "</user_uploaded_content>"
    )


def run_ocr_solution(solution_text: str, solution_image) -> str:
    if not solution_image:
        if solution_text and solution_text.strip():
            return _wrap_untrusted(solution_text, "student_text")
        return "请上传解答图片或输入解答文字"
    b64, mime = encode_image_to_base64(solution_image)
    messages = [
        {"role": "system", "content": SOLUTION_VISION_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "请识别图片中的数学解答过程，保留步骤结构，为每步编号"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]},
    ]
    ocr_text = vision_chat(messages, temperature=0.1, max_tokens=2048)
    wrapped_ocr = _wrap_untrusted(ocr_text, "solution_image_ocr")
    if solution_text and solution_text.strip():
        wrapped_text = _wrap_untrusted(solution_text, "student_text")
        return f"{wrapped_text}\n\n[图片解答识别]:\n{wrapped_ocr}"
    return wrapped_ocr


def run_review(problem_text: str, problem_image, ocr_confirmed: str, progress=gr.Progress(track_tqdm=False)):
    """Generator: yield (review_md, ref_md, info_md) 更新。"""
    problem_img_path = problem_image if problem_image else None
    if not (problem_text and problem_text.strip()) and not problem_img_path:
        yield ("请输入题目文字或上传题目图片", "", "")
        return
    if not (ocr_confirmed and ocr_confirmed.strip()):
        yield ("请先识别或输入解答过程", "", "")
        return

    progress(0, desc="准备批改...")
    last_info = "⏳ 准备批改..."
    final_result = None

    try:
        for ev in review(
            problem=problem_text,
            image_path=problem_img_path,
            student_solution=ocr_confirmed,
            solution_image_path=None,
        ):
            info_md = _format_event_as_info(ev)
            last_info = info_md
            e = ev.get("event")
            if e == "final":
                final_result = ev["result"]
                break
            yield ("", "", last_info)
    except Exception as ex:
        yield (f"<div class='info-banner error'>❌ 批改失败: {ex}</div>", "", last_info)
        return

    if final_result is None:
        yield (f"<div class='info-banner warning'>⚠️ 批改未产出结果</div>", "", last_info)
        return

    difficulty = final_result.get("difficulty", "medium")
    final_info = f"✅ 完成 | 难度: {difficulty}"
    formatted_review = final_result.get("formatted_review") or ""
    standard_reference = final_result.get("standard_reference") or ""
    progress(1.0, desc="完成")
    yield (formatted_review, standard_reference, final_info)


# ==========================================================================
# UI 构建
# ==========================================================================

with gr.Blocks(title="MathSolver — 微积分与概率论解题智能体") as demo:
    # ===== Top Bar =====
    with gr.Row(elem_id="top-bar"):
        with gr.Column(scale=1, min_width=0):
            gr.HTML(
                '<div class="brand">'
                '<span class="brand-icon">∫</span>'
                '<span>MathSolver</span>'
                '<span class="brand-subtitle">— 微积分与概率论解题智能体</span>'
                '</div>'
            )
        with gr.Column(scale=0, min_width=48):
            gr.HTML(
                '<button id="theme-toggle" type="button" '
                'onclick="window.toggleTheme && window.toggleTheme()" '
                'title="切换主题">🌙</button>'
            )

    # ===== Tabs =====
    with gr.Tabs():
        # ----- 求解 Tab -----
        with gr.Tab("求解"):
            gr.Markdown(
                "**求解功能：** 智能求解微积分 / 概率论问题，结合 LLM 推理 + SymPy/scipy 代码执行 + MCP 工具。\n\n"
                "支持题目图片 OCR（自动识别数学公式）。进度实时显示。\n\n"
                "MCP 工具：符号运算 / 概率计算 / 交叉验证 / 绘图 / LaTeX 校验。"
            )
            with gr.Row():
                # 左：输入
                with gr.Column(scale=5, min_width=320):
                    solve_image_box = gr.Image(
                        type="filepath",
                        label="📷 题目图片（可选）",
                        sources=["upload", "clipboard"],
                        height=200,
                    )
                    solve_input_box = gr.Textbox(
                        label="题目文本",
                        placeholder="例如：求 f(x)=x^2*e^x 的不定积分\n（也可只上传图片，此处留空）",
                        lines=3,
                    )
                    with gr.Row():
                        solve_submit_btn = gr.Button("🚀 求解", variant="primary", scale=2)
                        solve_clear_btn = gr.Button("清空", scale=1)
                    gr.Markdown("### 示例题目（点击填入）")
                    solve_examples = gr.Dataset(
                        samples=[[ex[0]] for ex in SOLVE_EXAMPLES],
                        components=[solve_input_box],
                        label="",
                        samples_per_page=10,
                        layout="gallery",
                        elem_classes="examples-grid",
                    )
                    solve_examples.click(
                        lambda x: x[0] if x else "",
                        inputs=[solve_examples],
                        outputs=[solve_input_box],
                    )

                # 右：结果
                with gr.Column(scale=7, min_width=320):
                    solve_info_box = gr.Markdown(
                        value='<div class="empty-state"><div class="empty-state-icon">∫</div>点击「求解」开始</div>',
                        label="求解信息 / 进度",
                        elem_classes="math-content",
                    )
                    solve_solution_box = gr.Markdown(
                        label="完整解题过程（LaTeX 渲染）",
                        latex_delimiters=LATEX_DELIMITERS,
                        elem_classes="math-content",
                    )
                    solve_answer_box = gr.Markdown(
                        label="最终答案",
                        latex_delimiters=LATEX_DELIMITERS,
                        elem_classes="math-content",
                    )

            solve_submit_btn.click(
                fn=run_solve,
                inputs=[solve_input_box, solve_image_box],
                outputs=[solve_solution_box, solve_answer_box, solve_info_box],
            )
            solve_input_box.submit(
                fn=run_solve,
                inputs=[solve_input_box, solve_image_box],
                outputs=[solve_solution_box, solve_answer_box, solve_info_box],
            )
            solve_clear_btn.click(
                fn=lambda: ("", None, "", "", '<div class="empty-state"><div class="empty-state-icon">∫</div>已清空</div>'),
                inputs=None,
                outputs=[solve_input_box, solve_image_box, solve_solution_box, solve_answer_box, solve_info_box],
            )

        # ----- 批改 Tab -----
        with gr.Tab("解题批改"):
            gr.Markdown(
                "**解题批改流程：**\n\n"
                "1. 输入题目（文字/图片）+ 解答过程（文字/图片）\n"
                "2. 点击「识别解答」OCR 图片 → 修正识别结果\n"
                "3. 点击「确认并批改」→ 系统自动求解 + 逐步批改 + 元验证\n\n"
                "**基于论文：** PARC 前提链验证 + 5 类错误分类 + AskBD 多样性保护 + 元验证审查"
            )
            with gr.Row():
                with gr.Column(scale=5, min_width=320):
                    review_problem_image = gr.Image(
                        type="filepath",
                        label="📷 题目图片（可选）",
                        sources=["upload", "clipboard"],
                        height=160,
                    )
                    review_problem_text = gr.Textbox(
                        label="题目文字",
                        placeholder="例如：求 ∫x²eˣdx",
                        lines=2,
                    )
                    gr.Markdown("---")
                    review_solution_image = gr.Image(
                        type="filepath",
                        label="📷 解答图片（可选）",
                        sources=["upload", "clipboard"],
                        height=160,
                    )
                    review_solution_text = gr.Textbox(
                        label="解答文字（也可先上传图片再点击识别）",
                        placeholder="例如：Step 1: ... Step 2: ...",
                        lines=4,
                    )
                    with gr.Row():
                        ocr_btn = gr.Button("🖼 识别解答", variant="secondary", scale=1)
                        review_grade_btn = gr.Button("🚀 确认并批改", variant="primary", scale=2)
                    review_ocr_result = gr.Textbox(
                        label="解答内容（识别结果，可手动修正）",
                        placeholder="OCR 识别后会填入此处，请修正后再批改",
                        lines=8,
                    )
                    gr.Markdown("### 批改示例（点击填入）")
                    review_examples = gr.Dataset(
                        samples=[[ex[0], ex[2]] for ex in REVIEW_EXAMPLES],
                        components=[review_problem_text, review_ocr_result],
                        label="",
                        samples_per_page=5,
                        layout="gallery",
                        elem_classes="examples-grid",
                    )
                    def _fill_review_ex(ex):
                        if not ex:
                            return "", ""
                        return ex[0] if len(ex) > 0 else "", ex[1] if len(ex) > 1 else ""
                    review_examples.click(
                        _fill_review_ex,
                        inputs=[review_examples],
                        outputs=[review_problem_text, review_ocr_result],
                    )

                with gr.Column(scale=7, min_width=320):
                    review_info_box = gr.Markdown(
                        value='<div class="empty-state"><div class="empty-state-icon">✏</div>点击「确认并批改」开始</div>',
                        label="批改信息 / 进度",
                        elem_classes="math-content",
                    )
                    review_output = gr.Markdown(
                        label="批改结果（LaTeX 渲染）",
                        latex_delimiters=LATEX_DELIMITERS,
                        elem_classes="math-content",
                    )
                    review_correct_ref = gr.Markdown(
                        label="正确解法参考（LaTeX 渲染）",
                        latex_delimiters=LATEX_DELIMITERS,
                        elem_classes="math-content",
                    )

            ocr_btn.click(
                fn=run_ocr_solution,
                inputs=[review_solution_text, review_solution_image],
                outputs=[review_ocr_result],
            )
            review_grade_btn.click(
                fn=run_review,
                inputs=[review_problem_text, review_problem_image, review_ocr_result],
                outputs=[review_output, review_correct_ref, review_info_box],
            )

    # ===== Footer =====
    gr.Markdown(
        "---\n"
        "**配置：** 在 `.env` 中设置 `API_BASE`, `API_KEY`, `VISION_MODEL_NAME`, `SOLVER_MODEL_NAME`, `MCP_SERVERS`\n\n"
        "**架构：** ToRA + SelfCheck 模式 · USC 自一致性 · Verify-First 纠错 · PARC 前提链验证 · 沙箱代码执行"
    )


if __name__ == "__main__":
    try:
        router = get_mcp_router()
        if router:
            print(f"MCP connected: {router.tool_count} tools available")
    except Exception as e:
        print(f"MCP pre-connect skipped: {e}")

    # Gradio 6.x：theme/css/head 改在 launch() 传
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=LinearLight(),
        css=CSS,
        head=HEAD,
    )
