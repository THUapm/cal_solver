"""LLM 客户端与图像 base64 编码工具。

变更（P0.2）：
- 启动期校验 API_KEY，非空才继续；缺则 raise SystemExit
- 包 _chat_with_retry：对 APIConnectionError / APITimeoutError / RateLimitError
  指数退避重试 max_retries 次
- 显式 httpx.Client timeout 避免请求挂起
- 每次 LLM 调用都显式传 timeout
"""

import base64
import logging
import os
import time
from io import BytesIO

import httpx
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from PIL import Image

load_dotenv()

API_BASE = os.getenv("API_BASE", "https://api.openai.com/v1")
API_KEY = os.getenv("API_KEY", "")
VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "gpt-4o")
SOLVER_MODEL_NAME = os.getenv("SOLVER_MODEL_NAME", "gpt-3.5-turbo")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.getenv("LLM_RETRY_BACKOFF", "1.0"))

RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)


def _validate_config() -> None:
    """启动期校验必需 env，缺则 raise SystemExit 给出友好提示。"""
    missing = []
    if not API_KEY or API_KEY.startswith("sk-REPLACE-ME"):
        missing.append("API_KEY")
    if not API_BASE:
        missing.append("API_BASE")
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\n请在 .env 文件中配置。参考 .env.example 模板。"
        )


_validate_config()

_http_client = httpx.Client(timeout=LLM_TIMEOUT)
client = OpenAI(base_url=API_BASE, api_key=API_KEY, http_client=_http_client)


def encode_image_to_base64(filepath: str) -> tuple[str, str]:
    """把图片文件编码为 (base64_str, mime_type) 元组。"""
    img = Image.open(filepath)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, "image/jpeg"


def _chat_with_retry(
    messages: list[dict],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    max_retries: int = LLM_MAX_RETRIES,
    operation: str = "chat",
) -> str:
    """OpenAI chat 调用 + 指数退避重试。

    抛出：
    - RuntimeError：所有 retry 耗尽后包装最后一次异常
    - APIError：非可重试错误（4xx 业务错误），立即抛出
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=LLM_TIMEOUT,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM returned empty content")
            return content
        except RETRYABLE_EXCEPTIONS as e:
            last_error = e
            if attempt < max_retries:
                backoff = LLM_RETRY_BACKOFF * (2 ** (attempt - 1))
                logging.warning(
                    f"[{operation}] attempt {attempt}/{max_retries} failed: "
                    f"{type(e).__name__}: {e}. Retrying in {backoff:.1f}s..."
                )
                time.sleep(backoff)
            else:
                logging.error(
                    f"[{operation}] all {max_retries} attempts failed: "
                    f"{type(e).__name__}: {e}"
                )
        except APIError as e:
            logging.error(f"[{operation}] non-retryable APIError: {e}")
            raise
    raise RuntimeError(
        f"LLM call '{operation}' failed after {max_retries} attempts: "
        f"{type(last_error).__name__ if last_error else 'Unknown'}: {last_error}"
    ) from last_error


def vision_chat(messages: list[dict], temperature: float = 0.1, max_tokens: int = 1024) -> str:
    return _chat_with_retry(
        messages,
        model=VISION_MODEL_NAME,
        temperature=temperature,
        max_tokens=max_tokens,
        operation="vision_chat",
    )


def solver_chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2048) -> str:
    return _chat_with_retry(
        messages,
        model=SOLVER_MODEL_NAME,
        temperature=temperature,
        max_tokens=max_tokens,
        operation="solver_chat",
    )
