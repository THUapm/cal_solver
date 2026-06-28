"""MathSolver — 微积分与概率论解题智能体

单列线性流 UI（Linear/Notion 系）。
- LinearLight / LinearDark 主题切换
- Inter / JetBrains Mono 字体 + KaTeX auto-render
- 流程: 题目上传→渲染确认 → 解答上传→批改(带置信度) → 举一反三
- 每步带颜色徽章(绿>=90+check / 黄70-89 / 红<70 或 cross)
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import gradio as gr

from src.agent import solve, review, generate_similar_problems, get_mcp_router
from src.llm_client import vision_chat, encode_image_to_base64
from src.prompts import VISION_SYSTEM_PROMPT, SOLUTION_VISION_PROMPT
from src.utils import classify_confidence_badge, parse_step_confidence, parse_step_correctness, parse_similar_problems, normalize_latex_for_katex, latex_to_html

ASSETS = Path(__file__).parent / "assets"
HEAD = (ASSETS / "head.html").read_text(encoding="utf-8")
CSS = (ASSETS / "style.css").read_text(encoding="utf-8")

_SESSION: dict = {"last_problem": "", "last_standard_reference": ""}

from assets.theme import LinearLight


# ==========================================================================
# Callbacks
# ==========================================================================

def do_ocr(problem_text, problem_image, progress=gr.Progress(track_tqdm=False)):
    """OCR 题目图片。结果写入预览区（HTML 渲染版），不覆盖题目文字。"""
    image_path = problem_image if problem_image else None
    if not image_path:
        if problem_text and problem_text.strip():
            return problem_text, latex_to_html(normalize_latex_for_katex(problem_text))
        return "", "<p><em>（请输入题目或上传图片）</em></p>"

    progress(0, desc="识别题目中...")
    b64, mime = encode_image_to_base64(image_path)
    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": problem_text if problem_text else "请识别图片中的数学问题"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]},
    ]
    ocr_text = vision_chat(messages)
    progress(1.0, desc="完成")
    return problem_text, latex_to_html(normalize_latex_for_katex(ocr_text))


def confirm_ocr(problem_text, ocr_preview):
    """把 OCR 预览写回题目文字。若已存在则追加。"""
    if not ocr_preview or not ocr_preview.strip():
        return problem_text
    if not problem_text or not problem_text.strip():
        return ocr_preview.strip()
    if problem_text.strip() == ocr_preview.strip():
        return problem_text
    return problem_text.rstrip() + "\n" + ocr_preview.strip()


def do_ocr_solution(solution_text, solution_image, progress=gr.Progress(track_tqdm=False)):
    """OCR 解答图片。直接替换原文字（不再追加），避免步骤重复。

    返回 (solution_text, solution_preview_html):
    - solution_text: 原始 OCR 文本, 用户可编辑
    - solution_preview_html: 渲染好的 MathML HTML, 写入 gr.HTML 组件
    """
    if not solution_image:
        if solution_text and solution_text.strip():
            return solution_text, latex_to_html(normalize_latex_for_katex(solution_text))
        return "", "<p><em>（上传图片并点击「识别解答图片」后, 在此显示渲染好的公式）</em></p>"
    progress(0, desc="识别解答中...")
    b64, mime = encode_image_to_base64(solution_image)
    messages = [
        {"role": "system", "content": SOLUTION_VISION_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "请识别图片中的数学解答过程，保留步骤结构，为每步编号"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]},
    ]
    ocr_text = vision_chat(messages, temperature=0.1, max_tokens=2048)
    progress(1.0, desc="完成")
    return ocr_text, latex_to_html(normalize_latex_for_katex(ocr_text))


def do_grade(problem_text, problem_img, solution_text, solution_img,
             progress=gr.Progress(track_tqdm=False)):
    """批改解答。Generator，yield (info_md, grade_md, ref_md, btn_similar_state)。"""
    problem_path = problem_img if problem_img else None
    solution_path = solution_img if solution_img else None

    if not (problem_text and problem_text.strip()) and not problem_path:
        yield ("请先输入题目或上传题目图片", "", "", gr.update(visible=True, interactive=False))
        return
    if not (solution_text and solution_text.strip()) and not solution_path:
        yield ("请先输入解答或上传解答图片", "", "", gr.update(visible=True, interactive=False))
        return

    progress(0, desc="开始批改...")
    last_info = "准备批改..."
    final_result = None
    accumulated_steps = []

    try:
        for ev in review(
            problem=problem_text,
            image_path=problem_path,
            student_solution=solution_text,
            solution_image_path=solution_path,
        ):
            e = ev.get("event")
            if e == "started":
                phase = ev.get("phase", "grading")
                if phase == "generating_reference":
                    last_info = "正在生成标准解法参考..."
                    progress(0.1, desc="生成参考解...")
                    yield (last_info, "", "", gr.update(visible=True, interactive=False))
            elif e == "ocr_running":
                last_info = f"识别 {ev.get('source', '?')} 图片中..."
                yield (last_info, "", "", gr.update(visible=True, interactive=False))
            elif e == "ocr_done":
                last_info = f"{ev.get('source', '?')} 图片识别完毕"
                yield (last_info, "", "", gr.update(visible=True, interactive=False))
            elif e == "reference_ready":
                last_info = f"参考解已生成 | 难度: {ev.get('difficulty', '?')}"
                progress(0.2, desc="批改中...")
                yield (last_info, "", "", gr.update(visible=True, interactive=False))
            elif e == "premise_extracting":
                last_info = f"提取第 {ev.get('step')}/{ev.get('n', '?')} 步前提中..."
                yield (last_info, "", "", gr.update(visible=True, interactive=False))
            elif e == "grading_step":
                last_info = f"批改第 {ev.get('step')}/{ev.get('n', '?')} 步..."
                progress(0.3 + 0.5 * (ev.get('step', 1) / max(ev.get('n', 1), 1)),
                         desc=f"批改 {ev.get('step')}/{ev.get('n', '?')}")
                yield (last_info, "", "", gr.update(visible=True, interactive=False))
            elif e == "step_graded":
                accumulated_steps.append({
                    "step": ev.get("step"),
                    "confidence": ev.get("confidence", 0),
                    "is_correct": ev.get("is_correct", False),
                })
                grade_html = latex_to_html(_format_steps_with_badges(accumulated_steps))
                yield (last_info, grade_html, "", gr.update(visible=True, interactive=False))
            elif e == "meta_checking":
                last_info = "元验证中（检查批改是否有幻觉）..."
                yield (last_info, latex_to_html(_format_steps_with_badges(accumulated_steps)), "",
                       gr.update(visible=True, interactive=False))
            elif e == "final":
                final_result = ev["result"]
                break
            else:
                yield (last_info, latex_to_html(_format_steps_with_badges(accumulated_steps)), "",
                       gr.update(visible=True, interactive=False))
    except Exception as ex:
        yield (f"批改失败: {ex}",
               latex_to_html(_format_steps_with_badges(accumulated_steps)), "",
               gr.update(visible=True, interactive=True))
        return

    if final_result is None:
        yield ("批改未产出结果", latex_to_html(_format_steps_with_badges(accumulated_steps)), "",
               gr.update(visible=True, interactive=True))
        return

    formatted_review = final_result.get("formatted_review") or ""
    grading_result = final_result.get("grading_result") or ""
    standard_reference = final_result.get("standard_reference") or ""
    difficulty = final_result.get("difficulty", "medium")
    _SESSION["last_problem"] = final_result.get("problem") or problem_text or ""
    _SESSION["last_standard_reference"] = standard_reference
    last_info = f"批改完成 | 难度: {difficulty}"
    progress(1.0, desc="完成")

    final_conf = parse_step_confidence(grading_result or formatted_review)
    final_correct = parse_step_correctness(grading_result or formatted_review)
    seen_final_steps = {s.get("step") for s in accumulated_steps}
    for step_num in sorted(final_conf):
        if step_num not in seen_final_steps:
            accumulated_steps.append({
                "step": step_num,
                "confidence": final_conf[step_num],
                "is_correct": final_correct.get(step_num, False),
            })

    grade_md = _format_steps_with_badges(accumulated_steps) + "\n\n---\n\n" + formatted_review
    grade_html = latex_to_html(normalize_latex_for_katex(grade_md))
    ref_html = latex_to_html(normalize_latex_for_katex(standard_reference))
    yield (last_info, grade_html, ref_html, gr.update(visible=True, interactive=True))


def do_similar(problem_text, progress=gr.Progress(track_tqdm=False)):
    """举一反三：抽取知识点 + 生成 3 道相似题。Generator。

    优先使用批改时缓存的 combined_problem（来自 OCR + 用户输入拼接），
    回退到当前 problem_text，避免 OCR 后未点"确认正确"时举一反三拿不到题面。
    """
    effective_problem = _SESSION.get("last_problem") or problem_text
    if not effective_problem or not effective_problem.strip():
        yield ("请先完成题目批改（OCR 后请点「✓ 确认正确」将题面写入输入框）", "", gr.update(visible=True))
        return

    progress(0, desc="抽取知识点...")
    final_result = None
    last_info = "准备举一反三..."

    try:
        for ev in generate_similar_problems(effective_problem, n=3):
            e = ev.get("event")
            if e == "knowledge_extracting":
                last_info = "抽取题目知识点..."
                yield (last_info, "", gr.update(visible=True))
            elif e == "knowledge_extracted":
                progress(0.3, desc="生成相似题...")
                last_info = "知识点抽取完毕"
                yield (last_info, "", gr.update(visible=True))
            elif e == "generating_similar":
                last_info = "生成相似题中..."
                yield (last_info, "", gr.update(visible=True))
            elif e == "similar_done":
                last_info = "相似题生成完毕"
                progress(0.9, desc="整理中...")
            elif e == "final":
                final_result = ev["result"]
                break
    except Exception as ex:
        yield (f"生成失败: {ex}", "", gr.update(visible=True))
        return

    if final_result is None:
        yield ("生成未产出结果", "", gr.update(visible=True))
        return

    kp = final_result.get("knowledge_points", "")
    sim_text = final_result.get("similar_problems", "")
    formatted = _format_similar_problems(kp, sim_text)
    formatted_html = latex_to_html(normalize_latex_for_katex(formatted))
    progress(1.0, desc="完成")
    yield ("完成", formatted_html, gr.update(visible=True))


# ==========================================================================
# Formatters
# ==========================================================================

def _format_steps_with_badges(steps: list) -> str:
    """把 step_graded 事件累积结果格式化为带彩色徽章的 Markdown。"""
    if not steps:
        return ""
    seen = set()
    unique = []
    for s in steps:
        sn = s.get("step")
        if sn in seen:
            continue
        seen.add(sn)
        unique.append(s)
    steps = unique
    lines = ["### 逐步批改（含置信度）", ""]
    for s in steps:
        conf = s.get("confidence", 0)
        correct = s.get("is_correct", False)
        badge_class = classify_confidence_badge(conf, correct)
        if badge_class == "correct-high":
            badge_emoji = "🟢"
        elif badge_class == "correct-med":
            badge_emoji = "🟡"
        else:
            badge_emoji = "🔴"
        status = "✓" if correct else "✗"
        lines.append(
            f"{badge_emoji} **Step {s.get('step')}** "
            f"<span class='step-badge {badge_class}'>{status} 置信度 {conf}%</span>"
        )
    return "\n".join(lines)


def _format_similar_problems(knowledge_points: str, similar_text: str) -> str:
    """把知识点+相似题格式化为 Markdown。"""
    parts = ["### 知识点清单", "", knowledge_points.strip(), "",
             "### 相似练习题", ""]
    problems = parse_similar_problems(similar_text)
    if not problems:
        parts.append(similar_text.strip())
    else:
        for p in problems:
            parts.append(f"**题目 {p['index']}**: {p['problem']}")
            parts.append(f"**答案**: {p['answer']}")
            parts.append("")
    return "\n".join(parts)


# ==========================================================================
# UI
# ==========================================================================

with gr.Blocks(
    title="MathSolver — 微积分与概率论解题智能体",
) as demo:

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
                '<button id="theme-toggle" onclick="toggleTheme()">🌙</button>',
            )

    # ===== Section 1: 题目上传 =====
    with gr.Group(elem_classes="section"):
        gr.HTML(
            '<div class="section-header">'
            '  <div class="section-icon">📐</div>'
            '  <div class="section-titles">'
            '    <div class="section-title">题目输入</div>'
            '    <div class="section-desc">上传题目图片或直接输入 TeX 题目</div>'
            '  </div>'
            '  <div class="section-step"><span class="step-num">01</span> / 04</div>'
            '</div>'
        )
        with gr.Row():
            with gr.Column(scale=1, min_width=0):
                problem_image = gr.Image(
                    type="filepath", label="题目图片（可选）",
                    sources=["upload", "clipboard"], height=200, buttons=[],
                    elem_classes="image-zone",
                )
            with gr.Column(scale=1, min_width=0):
                problem_text = gr.Textbox(
                    label="题目文字（TeX / 自然语言）",
                    placeholder="例如：求 ∫x²eˣdx", lines=4,
                )
                with gr.Row():
                    btn_ocr = gr.Button("🔍 识别图片", variant="secondary", scale=1)
                    btn_confirm = gr.Button("✓ 确认正确", variant="primary", scale=1)
                    btn_reocr = gr.Button("🔄 重新识别", scale=1)
        ocr_preview = gr.HTML(
            value="<p><em>（请上传图片或输入 TeX 题目）</em></p>",
            label="识别预览",
            elem_classes="math-content",
        )
        with gr.Row(elem_classes="examples-chips"):
            gr.Examples(
                examples=[
                    ["求 ∫₀^∞ x² e^{-x} dx 的值"],
                    ["设 X ~ B(10, 0.3)，求 P(X ≤ 2)"],
                    ["证明 ∫ₐᵇ f(x) dx + ∫_{f(a)}^{f(b)} f⁻¹(y) dy = b·f(b) − a·f(a)"],
                    ["求 ∑_{n=1}^∞ 1/n² 的值"],
                    ["求解 ODE y' + 2y = e^{-x}，y(0) = 1"],
                    ["若 P(A)=0.6, P(B)=0.5, P(A|B)=0.7，求 P(A∪B)"],
                ],
                inputs=[problem_text],
                label="示例题目（点击填入）",
            )

    # ===== Section 2: 解答上传 =====
    with gr.Group(elem_classes="section"):
        gr.HTML(
            '<div class="section-header">'
            '  <div class="section-icon">✏️</div>'
            '  <div class="section-titles">'
            '    <div class="section-title">解答上传</div>'
            '    <div class="section-desc">上传手写/电子解答，系统自动识别步骤</div>'
            '  </div>'
            '  <div class="section-step"><span class="step-num">02</span> / 04</div>'
            '</div>'
        )
        with gr.Row():
            with gr.Column(scale=1, min_width=0):
                solution_image = gr.Image(
                    type="filepath", label="解答图片（可选）",
                    sources=["upload", "clipboard"], height=240, buttons=[],
                    elem_classes="image-zone",
                )
            with gr.Column(scale=1, min_width=0):
                solution_text = gr.Textbox(
                    label="解答文字（可先上传图片再点识别）",
                    placeholder="例如：\nStep 1: 令 $u=x$, $dv=e^x dx$\nStep 2: 则 $du=dx$, $v=e^x$\nStep 3: 由分部积分 $\\int udv = uv - \\int vdu$",
                    lines=7,
                )
                btn_ocr_sol = gr.Button("🔍 识别解答图片", variant="secondary")
                btn_grade = gr.Button("🚀 开始批改", variant="primary", elem_classes="btn-grade")
        solution_preview = gr.HTML(
            value="<p><em>（上传图片并点击「识别解答图片」后, 在此显示渲染好的公式）</em></p>",
            label="解答预览（公式渲染）",
            elem_classes="math-content",
        )

    # ===== Section 3: 批改结果 =====
    with gr.Group(elem_classes="section"):
        gr.HTML(
            '<div class="section-header">'
            '  <div class="section-icon">📋</div>'
            '  <div class="section-titles">'
            '    <div class="section-title">批改结果</div>'
            '    <div class="section-desc">逐步批改 + 置信度 + 元验证</div>'
            '  </div>'
            '  <div class="section-step"><span class="step-num">03</span> / 04</div>'
            '</div>'
        )
        grade_info = gr.Markdown(
            value="*（点击「开始批改」后显示）*",
            label="批改进度",
            elem_classes="math-content",
        )
        grade_result = gr.HTML(
            value="",
            label="逐步批改（含置信度）",
            elem_classes="math-content",
        )
        standard_ref = gr.HTML(
            value="",
            label="标准解法参考",
            elem_classes="math-content",
        )
        btn_similar = gr.Button("📚 举一反三", variant="secondary",
                                visible=True, interactive=False,
                                elem_classes="btn-similar")

    # ===== Section 4: 相似题 =====
    similar_card = gr.Group(elem_classes="section", visible=False)
    with similar_card:
        gr.HTML(
            '<div class="section-header">'
            '  <div class="section-icon">📚</div>'
            '  <div class="section-titles">'
            '    <div class="section-title">相似练习题</div>'
            '    <div class="section-desc">基于题目的知识点生成的拓展练习</div>'
            '  </div>'
            '  <div class="section-step"><span class="step-num">04</span> / 04</div>'
            '</div>'
        )
        similar_info = gr.Markdown(
            value="", label="生成进度",
            elem_classes="math-content",
        )
        similar_result = gr.HTML(
            value="", label="生成结果",
            elem_classes="math-content",
        )

    # ===== Footer =====
    gr.Markdown(
        "---\n"
        "<sub>MathSolver · Powered by LLM + KaTeX · 配置请见 .env</sub>",
        elem_classes="footer-mini",
    )

    # ===== Event wiring =====
    problem_image.change(
        fn=do_ocr,
        inputs=[problem_text, problem_image],
        outputs=[problem_text, ocr_preview],
    )
    btn_ocr.click(
        fn=do_ocr,
        inputs=[problem_text, problem_image],
        outputs=[problem_text, ocr_preview],
    )
    btn_confirm.click(
        fn=confirm_ocr,
        inputs=[problem_text, ocr_preview],
        outputs=[problem_text],
    )
    btn_reocr.click(
        fn=do_ocr,
        inputs=[problem_text, problem_image],
        outputs=[problem_text, ocr_preview],
    )
    btn_ocr_sol.click(
        fn=do_ocr_solution,
        inputs=[solution_text, solution_image],
        outputs=[solution_text, solution_preview],
    )
    btn_grade.click(
        fn=do_grade,
        inputs=[problem_text, problem_image, solution_text, solution_image],
        outputs=[grade_info, grade_result, standard_ref, btn_similar],
    )
    btn_similar.click(
        fn=do_similar,
        inputs=[problem_text],
        outputs=[similar_info, similar_result, similar_card],
    )


if __name__ == "__main__":
    try:
        router = get_mcp_router()
        if router:
            print(f"MCP connected: {router.tool_count} tools available")
    except Exception as e:
        print(f"MCP pre-connect skipped: {e}")

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=LinearLight(),
        css=CSS,
        head=HEAD,
        inbrowser=True,
        show_error=True,
    )
