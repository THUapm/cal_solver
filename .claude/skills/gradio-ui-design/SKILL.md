---
name: gradio-ui-design
description: Gradio 5.x/6.x UI 设计规范 — Linear/Notion 现代产品风，含色板、字体、组件、KaTeX 集成、Examples 卡片化、暗色主题。适用于后端是 Python 一体化（FastAPI/Flask 不必分离时）的项目。
---

# Gradio UI Design — 现代产品风（Linear/Notion 系）

## 适用场景
- 后端是 Python 一体化（不需要单独拆 FastAPI）
- 快速产出精致 demo，不想引入完整 JS 栈（React/Vue/Next.js）
- 数学 / 科研 / 教学类应用（公式渲染 + 信息密度大）
- 内部工具 / 论文 demo / 教学平台

## 不适用场景
- 需要复杂交互动效（拖拽编辑器、实时协作、复杂动画）
- 需要 SSR / SEO（Gradio 不友好）
- 需要 PWA / 移动端深度优化（Gradio 移动端能用但不极致）

---

## 1. 设计 Token

### 1.1 颜色（Light）
```
--primary:        #5E6AD2
--primary-hover:  #6872D9
--primary-active: #525BC9
--primary-soft:   #EEEEFB

--surface:        #FFFFFF
--surface-alt:    #FAFAFA
--surface-elev:   #FFFFFF
--overlay:        rgba(0, 0, 0, 0.5)

--border:         #E4E4E7
--border-strong:  #D4D4D8
--border-focus:   rgba(94, 106, 210, 0.4)

--text:           #18181B
--text-muted:     #71717A
--text-subtle:    #A1A1AA
--text-inverse:   #FFFFFF

--success:        #10B981
--warning:        #F59E0B
--error:          #EF4444
--info:           #3B82F6
```

### 1.2 颜色（Dark）
```
--primary:        #6872D9
--primary-hover:  #7B85DD
--primary-active: #5E6AD2
--primary-soft:   #1E1E2E

--surface:        #0A0A0A
--surface-alt:    #18181B
--surface-elev:   #1F1F23
--overlay:        rgba(0, 0, 0, 0.7)

--border:         #27272A
--border-strong:  #3F3F46
--border-focus:   rgba(94, 106, 210, 0.5)

--text:           #FAFAFA
--text-muted:     #A1A1AA
--text-subtle:    #71717A
--text-inverse:   #18181B

--success:        #34D399
--warning:        #FBBF24
--error:          #F87171
--info:           #60A5FA
```

### 1.3 排版
- 正文：Inter Variable（Google Fonts，weights 400/500/600/700）
- 代码 / LaTeX：JetBrains Mono（weights 400/500）
- KaTeX：默认样式（已被 `currentColor` 覆盖，自动适应主题）

字号阶梯（rem）：
```
xs: 0.75rem  (12px) — label
sm: 0.875rem (14px) — body small
base: 1rem   (16px) — body
lg: 1.25rem  (20px) — subheading
xl: 1.5rem   (24px) — heading
2xl: 2rem    (32px) — title
```

### 1.4 间距（4pt 网格）
```
1: 4px    2: 8px    3: 12px    4: 16px
6: 24px   8: 32px   12: 48px   16: 64px
```

### 1.5 圆角
```
xs: 4px   (chip)
sm: 6px   (input)
md: 8px   (button)
lg: 12px  (card)
xl: 16px  (modal)
```

### 1.6 阴影
```css
/* hover 微阴影 */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04)

/* 浮起 */
--shadow-md: 0 4px 12px rgba(0, 0, 0, 0.06)

/* 高浮起 */
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08)

/* 暗色用更深的不透明度 */
.dark { --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.3); }
```

---

## 2. 组件模式

### 2.1 主题（Gradio 5.x/6.x）
继承 `gr.themes.Base`，覆盖核心 token：

```python
import gradio as gr

class LinearLight(gr.themes.Base):
    def __init__(self):
        super().__init__(
            primary_hue=gr.themes.colors.indigo,
            secondary_hue=gr.themes.colors.slate,
            neutral_hue=gr.themes.colors.zinc,
            radius_size=gr.themes.sizes.radius_md,
            font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "sans-serif"],
            font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
        )
        super().set(
            body_background_fill="#FFFFFF",
            block_background_fill="#FAFAFA",
            block_border_width="1px",
            block_border_color="#E4E4E7",
            block_radius="12px",
            button_primary_background_fill="#5E6AD2",
            button_primary_background_fill_hover="#6872D9",
            button_primary_text_color="#FFFFFF",
            button_primary_radius="8px",
            input_border_color="#E4E4E7",
            input_border_color_focus="#5E6AD2",
            input_radius="8px",
        )
```

### 2.2 暗色主题
继承 light，覆盖 `*_dark` token：

```python
class LinearDark(LinearLight):
    def __init__(self):
        super().__init__()
        super().set(
            body_background_fill="#0A0A0A",
            body_background_fill_dark="#0A0A0A",
            block_background_fill="#18181B",
            block_background_fill_dark="#18181B",
            block_border_color="#27272A",
            block_border_color_dark="#27272A",
            button_primary_background_fill="#6872D9",
            button_primary_background_fill_dark="#6872D9",
            button_primary_background_fill_hover="#7B85DD",
            button_primary_background_fill_hover_dark="#7B85DD",
            input_border_color="#27272A",
            input_border_color_dark="#27272A",
            input_border_color_focus="#6872D9",
            input_border_color_focus_dark="#6872D9",
        )
```

### 2.3 字体注入（`head.html`）
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### 2.4 KaTeX 集成（`head.html`）
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
        onload="renderMathInDocument()"></script>
<script>
let mathRenderScheduled = false;
function renderMathInDocument() {
  if (mathRenderScheduled) return;
  mathRenderScheduled = true;
  requestAnimationFrame(() => {
    document.querySelectorAll('.prose, .md, .math-content').forEach(el => {
      if (typeof renderMathInElement === 'function' && !el.dataset.mathRendered) {
        renderMathInElement(el, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\[', right: '\\]', display: true},
            {left: '\\(', right: '\\)', display: false}
          ],
          throwOnError: false
        });
        el.dataset.mathRendered = '1';
      }
    });
    mathRenderScheduled = false;
  });
}
// Gradio 重建 DOM 时触发
new MutationObserver(renderMathInDocument).observe(
  document.body, {childList: true, subtree: true}
);
// 初次加载
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', renderMathInDocument);
} else {
  renderMathInDocument();
}
</script>
```

### 2.5 主题切换按钮（client-side）
```python
theme_toggle = gr.Button("🌙", elem_id="theme-toggle", size="sm")
theme_toggle.click(
    None, None, None,
    js="""() => {
        const html = document.documentElement;
        const isDark = html.dataset.theme === 'dark';
        html.dataset.theme = isDark ? 'light' : 'dark';
        document.getElementById('theme-toggle').textContent = isDark ? '🌙' : '☀';
    }"""
)
```

CSS 配合（用 `data-theme` 属性选择器）：
```css
:root[data-theme="dark"] { --primary: #6872D9; ... }
```

### 2.6 Examples 卡片化（`gr.Dataset` + CSS 覆盖）
```python
examples_dataset = gr.Dataset(
    samples=[[ex] for ex in EXAMPLES],
    components=[solve_input_box],
    label="示例题目",
    samples_per_page=10,
    layout="gallery",
    elem_classes="examples-grid",
)
examples_dataset.click(
    lambda x: x[0] if x else "",
    inputs=[examples_dataset],
    outputs=[solve_input_box],
)
```

CSS：
```css
.examples-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.examples-grid button {
  text-align: left;
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-alt);
  transition: all 0.15s ease;
}
.examples-grid button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--primary);
}
```

### 2.7 进度 yield 模式（UI 配合 agent generator）
agent 现在 `yield` 事件，UI 用 `gr.Progress` + generator 函数更新：

```python
def run_solve(problem, image, progress=gr.Progress()):
    progress(0, desc="准备求解...")
    accumulated = ""
    for ev in solve(problem, image_path=image):
        if ev["event"] == "step_start":
            progress(ev["i"]/ev["n"], desc=f"Step {ev['i']}/{ev['n']}: {ev['label']}")
        elif ev["event"] == "step_done":
            accumulated += "\n\n" + ev["content"]
            yield accumulated, "", _format_event_as_info(ev)
        elif ev["event"] == "final":
            r = ev["result"]
            yield r["formatted_solution"], r["final_answer"], f"✅ 完成"
            return
        else:
            yield accumulated, "", _format_event_as_info(ev)
```

事件到 info 文案映射：
```python
EVENT_INFO = {
    "step_start":   lambda e: f"⏳ Step {e['i']}/{e['n']}: {e['label']}",
    "code_executing": lambda e: f"🔧 Step {e['i']} 执行代码中...",
    "code_done":    lambda e: f"✓ Step {e['i']} 代码完成",
    "mcp_calling":  lambda e: f"🔌 Step {e['i']} 调用 {e['tool']}...",
    "mcp_done":     lambda e: f"✓ Step {e['i']} MCP 完成",
    "verifying":    lambda e: f"🔍 验证中 (try {e.get('i', 1)})...",
    "verify_passed": lambda e: "✓ 验证通过",
    "verify_failed": lambda e: f"⚠️ 验证失败，纠错中...",
    "correcting":   lambda e: f"🔧 纠正中 (try {e['i']})...",
    "usc_path_start": lambda e: f"🧠 USC path {e['i']}/{e['n']} (temp={e['temp']:.2f})",
    "usc_agreement": lambda e: f"✓ USC 早退 (a={e['a']}, b={e['b']})",
    "usc_selecting": lambda e: f"🧠 USC 选优中...",
}
```

---

## 3. Do

- ✅ 用 CSS 变量（`--primary`, `--surface` 等）做主题切换，避免硬编码
- ✅ 所有 SVG icon 用 stroke 而非 fill，便于 currentColor
- ✅ 阴影在暗色主题下加深不透明度（避免看不见）
- ✅ 长 Markdown 输出用 `max-height` + 内部滚动
- ✅ `font-feature-settings: "cv11", "ss01"` 启用 Inter 视觉特性
- ✅ 进度条用 `gr.Progress(track_tqdm=False)`，文本用单行 markdown
- ✅ Examples 用 `gr.Dataset` + `layout="gallery"` 替代 `gr.Examples`

## 4. Don't

- ❌ 不要用 emoji 当图标（一致性差，难以更换）
- ❌ 不要超过 3 个色相（primary + 1-2 个状态色）
- ❌ 不要用 100% 圆角按钮（除非 chip 类）
- ❌ 不要用饱和度 > 80% 的颜色（视觉疲劳）
- ❌ 不要在 button 内同时出现 icon + 长文本（移动端会折行）
- ❌ 不要让暗色主题直接 `filter: invert(1)`（KaTeX 公式会失真）
- ❌ 不要在 `head=` 中加载 > 200KB 的同步 JS（阻塞首屏）

---

## 5. 响应式断点

```css
/* Mobile: < 640px — 单列堆叠 */
@media (max-width: 640px) {
  .gr-row { flex-direction: column !important; }
  .examples-grid { grid-template-columns: 1fr; }
}

/* Tablet: 640-1024px — 简化双列 */
@media (min-width: 640px) and (max-width: 1024px) {
  .examples-grid { grid-template-columns: 1fr 1fr; }
}

/* Desktop: > 1024px — 完整布局 */
@media (min-width: 1024px) {
  .examples-grid { grid-template-columns: 1fr 1fr; }
  .gradio-container { max-width: 1280px; margin: 0 auto; }
}
```

---

## 6. 验证清单

每个新页面过一遍：

- [ ] 4 种宽度（375 / 768 / 1280 / 1920px）排版不破
- [ ] Light + dark 切换 token 全部生效
- [ ] KaTeX 公式在两种主题下都正常显示
- [ ] Examples 卡片可点击填入输入框
- [ ] 求解过程 UI 至少 5 次进度更新
- [ ] USC 早退触发时 UI 显示"早退"标记
- [ ] 对比度 WCAG AA 通过（文本对背景 ≥ 4.5:1）
- [ ] Lighthouse 移动端 ≥ 85
- [ ] KaTeX 加载失败时显示降级提示（不要白屏）
- [ ] 全部 4 套测试（test_p0_fixes / test_skills / test_examples / test_mcp）绿

---

## 7. 文件结构

```
project/
├── app.py                    # Gradio UI 入口
├── assets/
│   ├── theme.py              # LinearLight + LinearDark
│   ├── style.css             # 主样式表（覆盖 Gradio 默认）
│   ├── head.html             # 字体 + KaTeX + Observer
│   └── README.md             # 资源说明
└── .claude/
    └── skills/
        └── gradio-ui-design/
            └── SKILL.md      # 本文件
```

`app.py` 引入方式：
```python
from pathlib import Path
ASSETS = Path(__file__).parent / "assets"
HEAD = (ASSETS / "head.html").read_text(encoding="utf-8")
CSS = (ASSETS / "style.css").read_text(encoding="utf-8")
from assets.theme import LinearLight

with gr.Blocks(theme=LinearLight(), css=CSS, head=HEAD) as demo:
    ...
```

---

## 8. 已知 Gradio 版本差异

| 特性 | 4.x | 5.x | 6.x |
|---|---|---|---|
| `gr.Progress(track_tqdm=)` | ✓ | ✓ | ✓（参数保留） |
| `gr.Dataset(layout="gallery")` | 部分 | ✓ | ✓ |
| 暗色切换 client API | ✗ | 部分 | ✓ |
| `gr.themes.builder()` | ✓ | ✓ | ✓ |
| CSS 变量命名 | 旧 | 重构 | 稳定 |
| 默认主题 | Soft | Default | Default |

推荐使用 5.x+。本项目当前环境是 6.14，所有 API 兼容。
