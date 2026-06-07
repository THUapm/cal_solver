"""Linear/Notion 风格的自建 Gradio 主题。

LinearLight: 浅色，紫色主调 (#5E6AD2)，白底
LinearDark:  深色，深灰底，紫色主调 (#6872D9)

继承 gr.themes.Base，覆盖 ~30 个核心 token。所有 CSS 变量都从
SKILL.md 描述的色板映射过来，保持单一来源。

注意：
- Gradio 6.x 的 set() 没有 button_primary_radius / input_radius / code_text_color，
  这些走全局 radius_size 或者通过 style.css 覆盖。
- button_active 状态用 button_transform_active 表达。
"""

import gradio as gr


_FONT_INTER = [gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]
_FONT_MONO = [gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "Consolas", "monospace"]


class LinearLight(gr.themes.Base):
    """Linear/Notion 浅色主题。"""

    def __init__(self):
        super().__init__(
            primary_hue=gr.themes.colors.indigo,
            secondary_hue=gr.themes.colors.slate,
            neutral_hue=gr.themes.colors.zinc,
            radius_size=gr.themes.sizes.radius_md,
            font=_FONT_INTER,
            font_mono=_FONT_MONO,
        )
        super().set(
            body_background_fill="#FFFFFF",
            body_text_color="#18181B",
            body_text_color_subdued="#71717A",
            block_background_fill="#FAFAFA",
            block_border_color="#E4E4E7",
            block_border_width="1px",
            block_radius="12px",
            block_label_text_size="0.875rem",
            block_label_text_weight="500",
            block_label_margin="0 0 4px 0",
            block_label_padding="0",
            block_label_text_color="#18181B",
            block_title_text_weight="600",
            block_title_text_color="#18181B",
            block_padding="16px",
            button_primary_background_fill="#5E6AD2",
            button_primary_background_fill_hover="#6872D9",
            button_primary_text_color="#FFFFFF",
            button_primary_text_color_hover="#FFFFFF",
            button_primary_border_color="#5E6AD2",
            button_primary_border_color_hover="#6872D9",
            button_primary_shadow="0 1px 2px rgba(0, 0, 0, 0.04)",
            button_primary_shadow_hover="0 4px 12px rgba(94, 106, 210, 0.25)",
            button_secondary_background_fill="#FFFFFF",
            button_secondary_background_fill_hover="#FAFAFA",
            button_secondary_text_color="#18181B",
            button_secondary_text_color_hover="#18181B",
            button_secondary_border_color="#E4E4E7",
            button_secondary_border_color_hover="#D4D4D8",
            button_transform_hover="translateY(-1px)",
            input_background_fill="#FFFFFF",
            input_background_fill_focus="#FFFFFF",
            input_background_fill_hover="#FFFFFF",
            input_border_color="#E4E4E7",
            input_border_color_focus="#5E6AD2",
            input_border_color_hover="#D4D4D8",
            input_border_width="1px",
            input_padding="10px 12px",
            input_text_size="0.875rem",
            input_shadow="0 1px 2px rgba(0, 0, 0, 0.04)",
            input_shadow_focus="0 0 0 3px rgba(94, 106, 210, 0.15)",
            input_placeholder_color="#A1A1AA",
            link_text_color="#5E6AD2",
            link_text_color_hover="#6872D9",
            link_text_color_active="#525BC9",
            shadow_drop="0 1px 2px rgba(0, 0, 0, 0.04)",
            shadow_drop_lg="0 8px 24px rgba(0, 0, 0, 0.08)",
            block_shadow="0 1px 2px rgba(0, 0, 0, 0.04)",
            container_radius="12px",
            loader_color="#5E6AD2",
            slider_color="#5E6AD2",
            code_background_fill="#F4F4F5",
        )


class LinearDark(LinearLight):
    """Linear/Notion 深色主题。继承 Light，覆盖 _dark token。"""

    def __init__(self):
        super().__init__()
        super().set(
            body_background_fill="#0A0A0A",
            body_background_fill_dark="#0A0A0A",
            body_text_color="#FAFAFA",
            body_text_color_dark="#FAFAFA",
            body_text_color_subdued="#A1A1AA",
            body_text_color_subdued_dark="#A1A1AA",
            block_background_fill="#18181B",
            block_background_fill_dark="#18181B",
            block_border_color="#27272A",
            block_border_color_dark="#27272A",
            block_label_text_color="#FAFAFA",
            block_label_text_color_dark="#FAFAFA",
            block_title_text_color="#FAFAFA",
            block_title_text_color_dark="#FAFAFA",
            button_primary_background_fill="#6872D9",
            button_primary_background_fill_dark="#6872D9",
            button_primary_background_fill_hover="#7B85DD",
            button_primary_background_fill_hover_dark="#7B85DD",
            button_primary_border_color="#6872D9",
            button_primary_border_color_hover="#7B85DD",
            button_primary_shadow="0 1px 2px rgba(0, 0, 0, 0.3)",
            button_primary_shadow_hover="0 4px 12px rgba(124, 133, 221, 0.3)",
            button_secondary_background_fill="#18181B",
            button_secondary_background_fill_dark="#18181B",
            button_secondary_background_fill_hover="#27272A",
            button_secondary_background_fill_hover_dark="#27272A",
            button_secondary_text_color="#FAFAFA",
            button_secondary_text_color_hover="#FAFAFA",
            button_secondary_text_color_dark="#FAFAFA",
            button_secondary_text_color_hover_dark="#FAFAFA",
            button_secondary_border_color="#27272A",
            button_secondary_border_color_hover="#3F3F46",
            button_secondary_border_color_dark="#27272A",
            button_secondary_border_color_hover_dark="#3F3F46",
            input_background_fill="#18181B",
            input_background_fill_dark="#18181B",
            input_background_fill_focus="#1F1F23",
            input_background_fill_focus_dark="#1F1F23",
            input_background_fill_hover="#1F1F23",
            input_background_fill_hover_dark="#1F1F23",
            input_border_color="#27272A",
            input_border_color_dark="#27272A",
            input_border_color_focus="#6872D9",
            input_border_color_focus_dark="#6872D9",
            input_border_color_hover="#3F3F46",
            input_border_color_hover_dark="#3F3F46",
            input_placeholder_color="#71717A",
            input_placeholder_color_dark="#71717A",
            link_text_color="#7B85DD",
            link_text_color_dark="#7B85DD",
            link_text_color_hover="#9AA6E5",
            link_text_color_hover_dark="#9AA6E5",
            link_text_color_active="#5E6AD2",
            link_text_color_active_dark="#5E6AD2",
            code_background_fill="#27272A",
            code_background_fill_dark="#27272A",
            shadow_drop="0 1px 2px rgba(0, 0, 0, 0.3)",
            shadow_drop_lg="0 8px 24px rgba(0, 0, 0, 0.4)",
            block_shadow="0 1px 2px rgba(0, 0, 0, 0.3)",
            block_shadow_dark="0 1px 2px rgba(0, 0, 0, 0.3)",
            loader_color="#6872D9",
            loader_color_dark="#6872D9",
            slider_color="#6872D9",
            slider_color_dark="#6872D9",
        )
