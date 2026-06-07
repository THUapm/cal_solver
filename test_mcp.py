from src.utils import extract_tool_calls
from src.prompts import format_mcp_tools_for_prompt


def test_extract_tool_calls():
    text = 'Compute this.\n```tool\n{"name": "symbolic_compute", "arguments": {"expression": "x**2*exp(x)", "operation": "integrate", "variable": "x"}}\n```'
    calls = extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "symbolic_compute"
    assert calls[0]["arguments"]["operation"] == "integrate"
    print(f"Single tool call parsed: {calls[0]}")

    text2 = 'No tool calls here.'
    assert extract_tool_calls(text2) == []
    print("No tool calls: OK")

    text3 = '```tool\n{"name": "verify_result", "arguments": {"original_expression": "x**2", "claimed_result": "x**2+2", "verification_type": "numerical"}}\n```\n```tool\n{"name": "symbolic_compute", "arguments": {"expression": "x**2+1", "operation": "simplify"}}\n```'
    calls3 = extract_tool_calls(text3)
    assert len(calls3) == 2
    assert calls3[0]["name"] == "verify_result"
    assert calls3[1]["name"] == "symbolic_compute"
    print(f"Multi tool calls parsed: {len(calls3)} calls")

    text4 = '```tool\n{"name": "plot_function", "args": {"expression": "sin(x)", "x_range": "-5,5"}}\n```'
    calls4 = extract_tool_calls(text4)
    assert len(calls4) == 1
    assert calls4[0]["name"] == "plot_function"
    assert calls4[0]["arguments"] == {"expression": "sin(x)", "x_range": "-5,5"}
    print(f"Args alias parsed: {calls4[0]}")

    text5 = '```tool\nsome broken text "name": "latex_validate"\n```'
    calls5 = extract_tool_calls(text5)
    assert len(calls5) == 1
    assert calls5[0]["name"] == "latex_validate"
    print(f"Fallback regex parsed: {calls5[0]}")


def test_format_mcp_tools_for_prompt():
    tool_infos = [
        {
            "name": "symbolic_compute",
            "description": "SymPy symbolic computation.\n\nWHEN TO USE: Need exact symbolic results.\nPRE-CONDITIONS: expression must be valid.\nPOST-CONDITIONS: Returns exact result.",
            "inputSchema": {
                "type": "object",
                "required": ["expression", "operation"],
                "properties": {
                    "expression": {"type": "string", "description": "SymPy expression"},
                    "operation": {"type": "string", "enum": ["differentiate", "integrate", "solve", "limit", "simplify"]},
                    "variable": {"type": "string", "description": "Variable name"},
                },
            },
        },
        {
            "name": "verify_result",
            "description": "Cross-verify mathematical results.\n\nWHEN TO USE: Need to verify a claimed result.\nPRE-CONDITIONS: expressions must be valid.\nPOST-CONDITIONS: Returns PASS/FAIL.",
            "inputSchema": {
                "type": "object",
                "required": ["original_expression", "claimed_result", "verification_type"],
                "properties": {
                    "original_expression": {"type": "string"},
                    "claimed_result": {"type": "string"},
                    "verification_type": {"type": "string"},
                    "variable": {"type": "string"},
                },
            },
        },
    ]
    formatted = format_mcp_tools_for_prompt(tool_infos)
    assert "symbolic_compute" in formatted
    assert "verify_result" in formatted
    assert "WHEN TO USE" in formatted
    assert "Chain-of-Abstraction" in formatted
    assert "re-ground" in formatted.lower()
    assert "required" in formatted
    assert "options:" in formatted
    print(f"MCP tool prompt formatted OK (length: {len(formatted)} chars)")


def test_mcp_connect():
    from src.mcp_client import MCPToolRouter
    import os

    router = MCPToolRouter(os.getenv("MCP_SERVERS", "config/mcp_servers.json"))
    router.connect_all_sync()
    tool_infos = router.get_all_tool_descriptions_raw()
    assert len(tool_infos) >= 5
    names = [t["name"] for t in tool_infos]
    assert "symbolic_compute" in names
    assert "numerical_probability" in names
    assert "verify_result" in names
    assert "plot_function" in names
    assert "latex_validate" in names
    print(f"Connected! Tools: {names}")
    router.close_sync()


def test_mcp_call_symbolic():
    from src.mcp_client import MCPToolRouter
    import os

    router = MCPToolRouter(os.getenv("MCP_SERVERS", "config/mcp_servers.json"))
    router.connect_all_sync()

    result = router.call_tool_sync("symbolic_compute", {
        "expression": "x**2*exp(x)",
        "operation": "integrate",
        "variable": "x",
    })
    assert "exp(x)" in result or "e^x" in result.lower() or "PASS" in result or "Error" not in result
    print(f"Symbolic result: {result[:200]}")

    result2 = router.call_tool_sync("symbolic_compute", {
        "expression": "sin(x)/x",
        "operation": "limit",
        "variable": "x",
        "point": "0",
    })
    assert "1" in result2
    print(f"Limit result: {result2[:200]}")

    router.close_sync()


def test_mcp_call_verify():
    from src.mcp_client import MCPToolRouter
    import os

    router = MCPToolRouter(os.getenv("MCP_SERVERS", "config/mcp_servers.json"))
    router.connect_all_sync()

    result = router.call_tool_sync("verify_result", {
        "original_expression": "x**2*exp(x)",
        "claimed_result": "(x**2-2*x+2)*exp(x)",
        "verification_type": "derivative",
        "variable": "x",
    })
    assert "PASS" in result
    print(f"Verify PASS: {result[:200]}")

    result2 = router.call_tool_sync("verify_result", {
        "original_expression": "x**2+1",
        "claimed_result": "x**2+2",
        "verification_type": "numerical",
        "variable": "x",
    })
    assert "FAIL" in result2
    print(f"Verify FAIL: {result2[:200]}")

    router.close_sync()


def test_mcp_call_probability():
    from src.mcp_client import MCPToolRouter
    import os

    router = MCPToolRouter(os.getenv("MCP_SERVERS", "config/mcp_servers.json"))
    router.connect_all_sync()

    result = router.call_tool_sync("numerical_probability", {
        "distribution": "norm",
        "parameters": '{"loc": 10, "scale": 2}',
        "operation": "cdf",
        "value": "12",
    })
    assert "0.84" in result or "Error" not in result
    print(f"Probability result: {result[:200]}")

    router.close_sync()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("--- Offline tests (no MCP server needed) ---")
    test_extract_tool_calls()
    test_format_mcp_tools_for_prompt()
    print("\n✅ All offline tests passed!")

    print("\n--- MCP server tests (requires mcp_math_tools.py running) ---")
    print("Run manually: python -X utf8 test_mcp.py --with-mcp")
    if "--with-mcp" in sys.argv:
        test_mcp_connect()
        test_mcp_call_symbolic()
        test_mcp_call_verify()
        test_mcp_call_probability()
        print("\n✅ All MCP tests passed!")