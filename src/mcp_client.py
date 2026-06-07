import os
import sys
import json
import logging
import asyncio
import threading
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Windows 上 asyncio 默认 SelectorEventLoop 不支持 subprocess（stdio_client
# 通过 subprocess 启动 MCP server）。必须在第一次创建 event loop 之前
# 把策略切到 ProactorEventLoopPolicy，否则会抛 NotImplementedError。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class MCPToolRouter:
    """MCP管道层：连接外部MCP Server，发现工具，调用工具。
    
    不含RAG检索层 — 小工具集全量注入prompt。
    论文方法论(JTPRO 4层描述、re-grounding、CoA)融入prompt设计，不在本文件中。
    
    使用daemon thread + 长期event loop方案：
    所有async MCP操作在同一个event loop中执行，session可复用。
    """

    def __init__(self, config_path: str):
        self._config_path = config_path
        self._exit_stack: AsyncExitStack | None = None
        self._sessions: dict[str, ClientSession] = {}
        self._tool_info: dict[str, dict] = {}
        self._connected = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def connect_all_sync(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self._connect_all(), self._loop)
        future.result(timeout=30)

    def call_tool_sync(self, tool_name: str, arguments: dict) -> str:
        future = asyncio.run_coroutine_threadsafe(self._call_tool(tool_name, arguments), self._loop)
        return future.result(timeout=15)

    def close_sync(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self._close(), self._loop)
        try:
            future.result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    async def _connect_all(self) -> None:
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        config = json.load(open(self._config_path, encoding="utf-8"))
        for server_cfg in config.get("servers", []):
            server_name = server_cfg["name"]
            allowed = set(server_cfg.get("allowed_tools", []))

            try:
                server_params = StdioServerParameters(
                    command=server_cfg["command"],
                    args=server_cfg.get("args", []),
                    env=server_cfg.get("env", {}) or None,
                )
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                self._sessions[server_name] = session

                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    if allowed and tool.name not in allowed:
                        continue
                    self._tool_info[tool.name] = {
                        "server_name": server_name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema or {},
                    }

                logging.info(f"Connected to MCP server '{server_name}': {len(tools_result.tools)} tools discovered")

            except Exception as e:
                logging.warning(f"Failed to connect to MCP server '{server_name}': {e}")

        self._connected = True

    async def _call_tool(self, tool_name: str, arguments: dict) -> str:
        if tool_name not in self._tool_info:
            return f"Error: Tool '{tool_name}' not found or not authorized"

        server_name = self._tool_info[tool_name]["server_name"]
        schema = self._tool_info[tool_name]["inputSchema"]
        session = self._sessions.get(server_name)

        if session is None:
            return f"Error: Server '{server_name}' not connected"

        required = schema.get("required", []) if schema else []
        missing = [r for r in required if r not in arguments]
        if missing:
            return f"Error: Missing required arguments: {missing}"

        try:
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                texts = [c.text for c in result.content if hasattr(c, "text")]
                return "\n".join(texts) if texts else "Tool returned no output"
            return "Tool returned no output"
        except Exception as e:
            return f"Error calling tool '{tool_name}': {e}"

    async def _close(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
        self._sessions.clear()
        self._tool_info.clear()
        self._connected = False

    def get_all_tool_descriptions_raw(self) -> list[dict]:
        """返回所有已发现+已授权的工具信息，供prompts.py格式化注入。"""
        return [
            {"name": name, **info}
            for name, info in self._tool_info.items()
        ]

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def tool_count(self) -> int:
        return len(self._tool_info)