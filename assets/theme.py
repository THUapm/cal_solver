"""MathSolver — GitHub Primer 风格 Gradio 主题。

LinearLight / LinearDark 仍保留类名以保持向后兼容，但实际为 GitHub Primer 配色：
- 浅色：纯白 + GitHub 绿主色 + 浅灰输入框 + 6px 圆角
- 深色：GitHub Dark #0D1117 + 暗绿 #238636

继承 gr.themes.Base，覆盖核心 token。所有 CSS 变量都从 style.css 映射过来。
"""

import gradio as gr


_FONT_INTER = [gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]
_FONT_MONO = [gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "Consolas", "monospace"]


class LinearLight(gr.themes.Base):
    """GitHub Primer 浅色主题。"""

    def __init__(self):
        super().__init__(
            primary_hue=gr.themes.colors.green,
            secondary_hue=gr.themes.colors.blue,
            neutral_hue=gr.themes.colors.gray,
            radius_size=gr.themes.sizes.radius_sm,
            font=_FONT_INTER,
            font_mono=_FONT_MONO,
        )
        super().set(
            body_background_fill="#F6F8FA",
            body_text_color="#1F2328",
            body_text_color_subdued="#59636E",
            block_background_fill="#FFFFFF",
            block_border_color="#D0D7DE",
            block_border_width="1px",
            block_radius="10px",
            block_label_text_size="0.8125rem",
            block_label_text_weight="500",
            block_label_text_color="#59636E",
            block_label_margin="0 0 6px 0",
            block_title_text_weight="600",
            block_title_text_color="#1F2328",
            block_padding="24px 28px",
            button_primary_background_fill="#1F883D",
            button_primary_background_fill_hover="#1A7F37",
            button_primary_text_color="#FFFFFF",
            button_primary_text_color_hover="#FFFFFF",
            button_primary_border_color="rgba(31, 35, 40, 0.15)",
            button_primary_border_color_hover="rgba(31, 35, 40, 0.2)",
            button_primary_shadow="0 1px 0 rgba(31, 35, 40, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)",
            button_primary_shadow_hover="0 2px 4px rgba(31, 35, 40, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.1)",
            button_secondary_background_fill="#FFFFFF",
            button_secondary_background_fill_hover="#EAEEF2",
            button_secondary_text_color="#1F2328",
            button_secondary_text_color_hover="#1F2328",
            button_secondary_border_color="#D0D7DE",
            button_secondary_border_color_hover="#B1BAC4",
            button_transform_hover="translateY(-1px)",
            input_background_fill="#FFFFFF",
            input_background_fill_focus="#FFFFFF",
            input_background_fill_hover="#FFFFFF",
            input_border_color="#D0D7DE",
            input_border_color_focus="#0969DA",
            input_border_color_hover="#B1BAC4",
            input_border_width="1px",
            input_padding="8px 12px",
            input_text_size="0.875rem",
            input_shadow="0 1px 0 rgba(31, 35, 40, 0.02)",
            input_shadow_focus="0 0 0 3px rgba(9, 105, 218, 0.3)",
            input_placeholder_color="#818B98",
            link_text_color="#0969DA",
            link_text_color_hover="#0A4FA0",
            link_text_color_active="#0969DA",
            shadow_drop="0 1px 2px rgba(31, 35, 40, 0.06)",
            shadow_drop_lg="0 8px 24px rgba(31, 35, 40, 0.12)",
            block_shadow="0 1px 2px rgba(31, 35, 40, 0.04)",
            container_radius="10px",
            code_background_fill="#EAEEF2",
        )


class LinearDark(LinearLight):
    """GitHub Primer 深色主题。"""

    def __init__(self):
        super().__init__()
        super().set(
            body_background_fill="#0D1117",
            body_background_fill_dark="#0D1117",
            body_text_color="#E6EDF3",
            body_text_color_dark="#E6EDF3",
            body_text_color_subdued="#9198A1",
            body_text_color_subdued_dark="#9198A1",
            block_background_fill="#161B22",
            block_background_fill_dark="#161B22",
            block_border_color="#30363D",
            block_border_color_dark="#30363D",
            block_label_text_color="#9198A1",
            block_label_text_color_dark="#9198A1",
            block_title_text_color="#E6EDF3",
            block_title_text_color_dark="#E6EDF3",
            button_primary_background_fill="#238636",
            button_primary_background_fill_dark="#238636",
            button_primary_background_fill_hover="#2EA043",
            button_primary_background_fill_hover_dark="#2EA043",
            button_primary_border_color="rgba(240, 246, 252, 0.1)",
            button_primary_border_color_dark="rgba(240, 246, 252, 0.1)",
            button_primary_text_color="#FFFFFF",
            button_primary_text_color_dark="#FFFFFF",
            button_primary_shadow="0 1px 0 rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)",
            button_primary_shadow_hover="0 2px 4px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05)",
            button_secondary_background_fill="#161B22",
            button_secondary_background_fill_dark="#161B22",
            button_secondary_background_fill_hover="#21262D",
            button_secondary_background_fill_hover_dark="#21262D",
            button_secondary_text_color="#E6EDF3",
            button_secondary_text_color_hover="#E6EDF3",
            button_secondary_text_color_dark="#E6EDF3",
            button_secondary_text_color_hover_dark="#E6EDF3",
            button_secondary_border_color="#30363D",
            button_secondary_border_color_hover="#444C56",
            button_secondary_border_color_dark="#30363D",
            button_secondary_border_color_hover_dark="#444C56",
            input_background_fill="#0D1117",
            input_background_fill_dark="#0D1117",
            input_background_fill_focus="#161B22",
            input_background_fill_focus_dark="#161B22",
            input_background_fill_hover="#161B22",
            input_background_fill_hover_dark="#161B22",
            input_border_color="#30363D",
            input_border_color_dark="#30363D",
            input_border_color_focus="#2F81F7",
            input_border_color_focus_dark="#2F81F7",
            input_border_color_hover="#444C56",
            input_border_color_hover_dark="#444C56",
            input_placeholder_color="#6E7681",
            input_placeholder_color_dark="#6E7681",
            link_text_color="#2F81F7",
            link_text_color_dark="#2F81F7",
            link_text_color_hover="#58A6FF",
            link_text_color_hover_dark="#58A6FF",
            code_background_fill="#161B22",
            code_background_fill_dark="#161B22",
            shadow_drop="0 1px 2px rgba(0, 0, 0, 0.4)",
            shadow_drop_lg="0 8px 24px rgba(0, 0, 0, 0.6)",
            block_shadow="0 1px 2px rgba(0, 0, 0, 0.3)",
            block_shadow_dark="0 1px 2px rgba(0, 0, 0, 0.3)",
        )
