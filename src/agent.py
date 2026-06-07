import os
import json
import logging
import threading

from src.llm_client import vision_chat, solver_chat, encode_image_to_base64
from src.tools.executor import execute_code
from src.mcp_client import MCPToolRouter
from src.schemas import classify_schema, format_schema_injection_text
from src.prompts import (
    VISION_SYSTEM_PROMPT,
    SOLUTION_VISION_PROMPT,
    PREMISE_EXTRACTOR_PROMPT,
    build_solver_prompt,
    build_solver_prompt_with_skills,
    build_review_prompt,
    build_correction_prompt,
    build_usc_prompt,
    build_schema_injection,
    build_metacheck_prompt,
    format_mcp_tools_for_prompt,
    TOOL_RESULT_PROMPT,
    MCP_TOOL_RESULT_PROMPT,
    MAX_ITERATIONS_PROMPT,
    VERIFICATION_PROMPT,
)
from src.utils import (
    extract_code_blocks,
    extract_tool_calls,
    has_final_answer,
    format_iteration,
    format_solution,
    parse_solution_steps,
    parse_premise_json,
    detect_accumulation_errors,
    format_steps_with_premises,
    format_premise_links,
    extract_native_errors,
    format_review,
    parse_verification_errors,
    extract_final_answer_value,
    all_answers_agree,
    parse_usc_selection,
)

MAX_ITERATIONS = 5
MAX_CORRECTION_ITERATIONS = 2
MAX_REVIEW_ITERATIONS = 3

DIFFICULTY_CONFIG = {
    "easy":   {"max_iter": 2, "use_mcp": False, "use_self_consistency": False},
    "medium": {"max_iter": 5, "use_mcp": True,  "use_self_consistency": False},
    "hard":   {"max_iter": 5, "use_mcp": True,  "use_self_consistency": True},
}

REVIEW_CONFIG = {
    "easy":   {"max_iter": 1, "meta_check": False},
    "medium": {"max_iter": 2, "meta_check": "conditional"},
    "hard":   {"max_iter": 3, "meta_check": True},
}

EASY_KEYWORDS = ["求导数", "求不定积分", "求极限", "计算极限", "简单积分", "直接求", "basic", "求一阶导数", "导数", "不定积分", "极限", "求导"]
HARD_KEYWORDS = ["证明", "竞赛", "证明不等式", "综合", "多步", "同时求", "证明题", "IMO", "AIME", "putnam", "竞赛题", "偏导数", "泰勒展开", "高阶导数"]

_mcp_router: MCPToolRouter | None = None
_mcp_router_lock = threading.Lock()
_mcp_router_init_attempted = False


def _drain(generator) -> dict:
    """消费 generator 直到 final 事件，返回 result dict。

    用于 review() 内部调 solve() 拿参考解的场景：
    review 自己的事件流是给 UI 看的，solve() 的内部事件不应该泄漏出去。
    """
    final = None
    for ev in generator:
        if ev.get("event") == "final":
            final = ev["result"]
            break
    if final is None:
        raise RuntimeError("generator ended without 'final' event")
    return final


def get_mcp_router() -> MCPToolRouter | None:
    """获取 MCP router 单例（线程安全，双检查锁 + 失败短路）。

    Gradio 并发场景下多个 worker 会同时首次调用此函数，朴素 if-None 检查
    会导致重复连接。double-check + lock 保证只初始化一次。
    `_mcp_router_init_attempted` 标志位避免连接失败后每次请求都重试。
    """
    global _mcp_router, _mcp_router_init_attempted

    if _mcp_router is not None:
        return _mcp_router
    if _mcp_router_init_attempted:
        return None

    with _mcp_router_lock:
        if _mcp_router is not None:
            return _mcp_router
        if _mcp_router_init_attempted:
            return None
        _mcp_router_init_attempted = True

        config_path = os.getenv("MCP_SERVERS", "")
        if config_path and os.path.exists(config_path):
            try:
                router = MCPToolRouter(config_path)
                router.connect_all_sync()
                _mcp_router = router
                logging.info(f"MCP connected: {router.tool_count} tools available")
            except Exception as e:
                logging.warning(f"MCP connection failed: {e}")
        else:
            logging.info("No MCP_SERVERS config found, running without MCP tools")
        return _mcp_router


def estimate_difficulty(problem: str) -> str:
    problem_lower = problem.lower()
    easy_score = sum(1 for kw in EASY_KEYWORDS if kw.lower() in problem_lower)
    hard_score = sum(1 for kw in HARD_KEYWORDS if kw.lower() in problem_lower)
    if hard_score > 0:
        return "hard"
    if easy_score > 0 and hard_score == 0:
        return "easy"
    return "medium"


def solve(problem: str, image_path: str | None = None, fast: bool = False):
    """求解主入口。Generator，yield 进度事件，最后一个事件是 final。

    事件类型见 SKILL.md 或本文件内 _EVENT_* 字符串字面量。
    """
    combined_problem = problem

    if image_path:
        b64, mime = encode_image_to_base64(image_path)
        vision_messages = [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": problem if problem else "请识别图片中的数学问题"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ]
        image_description = vision_chat(vision_messages)
        wrapped_ocr = (
            '<user_uploaded_content source="image_ocr" trust="untrusted">\n'
            f"{image_description}\n"
            "</user_uploaded_content>"
        )
        if problem:
            combined_problem = f"{problem}\n\n{wrapped_ocr}"
        else:
            combined_problem = wrapped_ocr

    difficulty = estimate_difficulty(combined_problem)
    if fast:
        # 快速参考模式：用于 review() 生成对照解。跳过 USC + post-verification 纠错循环，
        # 把 max_iter 限制在 3。代价是参考解可能略不严谨，但成本下降 60%+。
        config = {
            "max_iter": 3,
            "use_mcp": difficulty != "easy",
            "use_self_consistency": False,
            "fast": True,
        }
    else:
        config = {**DIFFICULTY_CONFIG[difficulty], "fast": False}

    schema_info = classify_schema(combined_problem)

    yield {"event": "started", "difficulty": difficulty, "schema": schema_info["name"] if schema_info else None}

    if config["use_self_consistency"]:
        result = None
        for ev in solve_multi_path(combined_problem, config, schema_info):
            # 不转发子 generator 的 final 事件：solve() 自己会 yield 最终的 final
            if ev.get("event") == "final":
                result = ev["result"]
            else:
                yield ev
    else:
        result = None
        for ev in solve_single_path(combined_problem, config, schema_info):
            if ev.get("event") == "final":
                result = ev["result"]
            else:
                yield ev

    if result is not None:
        result["difficulty"] = difficulty
        result["schema"] = schema_info["name"] if schema_info else None
        yield {"event": "final", "result": result}


def solve_single_path(
    problem: str,
    config: dict,
    schema_info: dict | None,
    temperature_override: float | None = None,
):
    """单路径求解。Generator。"""
    router = get_mcp_router() if config["use_mcp"] else None
    mcp_tool_desc = ""
    if router:
        tool_infos = router.get_all_tool_descriptions_raw()
        mcp_tool_desc = format_mcp_tools_for_prompt(tool_infos)

    schema_text = ""
    if schema_info:
        schema_text = format_schema_injection_text(schema_info)

    system_prompt = build_solver_prompt_with_skills(
        mcp_tool_descriptions=mcp_tool_desc,
        schema_info=schema_text,
        verify_first=True,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": problem},
    ]

    all_steps = []
    final_answer = ""
    max_iter = config["max_iter"]

    temp = temperature_override if temperature_override is not None else 0.3

    for i in range(1, max_iter + 1):
        yield {"event": "step_start", "i": i, "n": max_iter, "label": "LLM 推理"}

        response = solver_chat(messages, temperature=temp, max_tokens=2048)
        messages.append({"role": "assistant", "content": response})

        code_blocks = extract_code_blocks(response)
        tool_calls = extract_tool_calls(response)

        if not code_blocks and not tool_calls and has_final_answer(response):
            all_steps.append(format_iteration(i, response, None))
            final_answer = response
            yield {"event": "step_done", "i": i, "content": all_steps[-1]}
            break

        exec_result = None
        if code_blocks:
            all_code = "\n".join(code_blocks)
            yield {"event": "code_executing", "i": i, "code": all_code}
            exec_result = execute_code(all_code)
            yield {
                "event": "code_done",
                "i": i,
                "success": exec_result["success"],
                "output": exec_result["output"],
            }
            tool_msg = TOOL_RESULT_PROMPT.format(output=exec_result["output"])
            messages.append({"role": "user", "content": tool_msg})

        mcp_results = None
        if tool_calls and router:
            mcp_results = []
            for tc in tool_calls:
                yield {
                    "event": "mcp_calling",
                    "i": i,
                    "tool": tc["name"],
                    "args": tc["arguments"],
                }
                mcp_result = router.call_tool_sync(tc["name"], tc["arguments"])
                yield {"event": "mcp_done", "i": i, "tool": tc["name"], "result": mcp_result}
                mcp_results.append({
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                    "result": mcp_result,
                })
                mcp_msg = MCP_TOOL_RESULT_PROMPT.format(
                    tool_result=f"Tool '{tc['name']}' called with: {json.dumps(tc['arguments'], ensure_ascii=False)}\nResult:\n{mcp_result}"
                )
                messages.append({"role": "user", "content": mcp_msg})
        elif tool_calls and not router:
            # tool call 但 router 不可用，提示 LLM 下一轮用本地 python
            mcp_msg = MCP_TOOL_RESULT_PROMPT.format(
                tool_result="[MCP-FALLBACK: NOT_CONNECTED] MCP 工具不可用，请改用 ```python``` 本地执行"
            )
            messages.append({"role": "user", "content": mcp_msg})

        all_steps.append(format_iteration(i, response, exec_result, mcp_results))
        yield {"event": "step_done", "i": i, "content": all_steps[-1]}

        if has_final_answer(response):
            final_answer = response
            break

        if i == max_iter:
            messages.append({"role": "user", "content": MAX_ITERATIONS_PROMPT})
            yield {"event": "step_start", "i": i + 1, "n": max_iter, "label": "汇总最终答案"}
            final_response = solver_chat(messages, temperature=temp, max_tokens=2048)
            all_steps.append(format_iteration(i + 1, final_response, None))
            yield {"event": "step_done", "i": i + 1, "content": all_steps[-1]}
            final_answer = final_response
            break

    # post-verification 阶段
    if final_answer and not config.get("fast", False):
        messages.append({"role": "user", "content": VERIFICATION_PROMPT})
        yield {"event": "verifying", "i": 1}
        verify_response = solver_chat(messages, temperature=0.1, max_tokens=2048)
        all_steps.append(format_iteration(len(all_steps) + 1, verify_response, None))
        yield {"event": "step_done", "i": len(all_steps), "content": all_steps[-1]}

        errors_found = parse_verification_errors(verify_response)
        if errors_found:
            yield {"event": "verify_failed", "errors": errors_found}
            for corr_iter in range(MAX_CORRECTION_ITERATIONS):
                yield {"event": "correcting", "i": corr_iter + 1, "errors": errors_found}
                correction_msg = build_correction_prompt(errors_found)
                messages.append({"role": "user", "content": correction_msg})
                corr_response = solver_chat(messages, temperature=0.2, max_tokens=2048)
                messages.append({"role": "assistant", "content": corr_response})

                corr_code = extract_code_blocks(corr_response)
                corr_tools = extract_tool_calls(corr_response)

                corr_exec = None
                if corr_code:
                    yield {"event": "code_executing", "i": f"corr_{corr_iter+1}", "code": "\n".join(corr_code)}
                    corr_exec = execute_code("\n".join(corr_code))
                    yield {
                        "event": "code_done",
                        "i": f"corr_{corr_iter+1}",
                        "success": corr_exec["success"],
                        "output": corr_exec["output"],
                    }
                    messages.append({"role": "user", "content": TOOL_RESULT_PROMPT.format(output=corr_exec["output"])})

                corr_mcp = None
                if corr_tools and router:
                    corr_mcp = []
                    for tc in corr_tools:
                        r = router.call_tool_sync(tc["name"], tc["arguments"])
                        corr_mcp.append({"name": tc["name"], "arguments": tc["arguments"], "result": r})
                        messages.append({"role": "user", "content": MCP_TOOL_RESULT_PROMPT.format(
                            tool_result=f"Tool '{tc['name']}' result:\n{r}"
                        )})

                all_steps.append(format_iteration(len(all_steps) + 1, corr_response, corr_exec, corr_mcp))
                yield {"event": "step_done", "i": len(all_steps), "content": all_steps[-1]}

                messages.append({"role": "user", "content": VERIFICATION_PROMPT})
                yield {"event": "verifying", "i": corr_iter + 2}
                reverify = solver_chat(messages, temperature=0.1, max_tokens=2048)
                all_steps.append(format_iteration(len(all_steps) + 1, reverify, None))
                yield {"event": "step_done", "i": len(all_steps), "content": all_steps[-1]}

                new_errors = parse_verification_errors(reverify)
                if not new_errors:
                    yield {"event": "verify_passed"}
                    final_answer = corr_response if has_final_answer(corr_response) else reverify
                    break
                yield {"event": "verify_failed", "errors": new_errors}
                errors_found = new_errors
        else:
            yield {"event": "verify_passed"}

    formatted = format_solution(all_steps, final_answer)

    yield {
        "event": "final",
        "result": {
            "problem": problem,
            "steps": all_steps,
            "full_solution": "\n\n".join(all_steps),
            "formatted_solution": formatted,
            "final_answer": final_answer,
        },
    }


def solve_multi_path(problem: str, config: dict, schema_info: dict | None, N: int = 3):
    """USC 多路径求解。Generator。B1 早退：前 2 路答案一致即停，不跑第 3 路。

    透传子路径所有事件，额外 yield 自己的 usc_path_start / usc_agreement / usc_selecting。
    """
    solutions = []
    for i in range(N):
        temp = 0.3 + 0.15 * i
        yield {"event": "usc_path_start", "i": i + 1, "n": N, "temp": temp}

        result = None
        for ev in solve_single_path(problem, config, schema_info, temperature_override=temp):
            # 不转发子 generator 的 final 事件：solve_multi_path 自己在循环外 yield
            if ev.get("event") == "final":
                result = ev["result"]
            else:
                yield ev
        solutions.append(result)

        # B1 早退：跑完第 2 路后检查前两路答案是否一致
        if i >= 1:
            answers = [extract_final_answer_value(s["final_answer"]) for s in solutions]
            if all_answers_agree(answers):
                yield {
                    "event": "usc_agreement",
                    "a": answers[0],
                    "b": answers[1],
                    "skipped": N - (i + 1),
                }
                final = solutions[0].copy()
                final["usc_early_exit"] = True
                final["all_answers"] = answers
                yield {"event": "final", "result": final}
                return

    # 3 路都不一致 → 让 solver 选优
    yield {"event": "usc_selecting", "n": N}
    solutions_text = ""
    for idx, s in enumerate(solutions, 1):
        ans = extract_final_answer_value(s["final_answer"]) or "(未找到最终答案)"
        final = s["final_answer"]
        # 保留末尾片段而非开头：boxed 答案与最终推理总在末尾，开头截断会丢掉关键信息
        excerpt = final[-1500:] if len(final) > 1500 else final
        solutions_text += f"\n**Solution {idx}** (extracted answer: {ans})\n{excerpt}\n"

    prompt = build_usc_prompt(problem, solutions_text, N)
    selection_response = solver_chat(
        [{"role": "system", "content": "You are a math solution selector."},
         {"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=512,
    )

    selected_idx = parse_usc_selection(selection_response)
    selected_idx = max(1, min(N, selected_idx)) - 1

    result = solutions[selected_idx]
    result["usc_selection"] = selection_response
    result["usc_selected_index"] = selected_idx + 1
    answers = [extract_final_answer_value(s["final_answer"]) for s in solutions]
    result["all_answers"] = answers
    yield {"event": "final", "result": result}


def review(
    problem: str,
    image_path: str | None = None,
    student_solution: str = "",
    solution_image_path: str | None = None,
):
    """批改主入口。Generator。"""
    combined_problem = problem
    combined_solution = student_solution
    image_description = None
    solution_ocr = None

    if image_path:
        yield {"event": "ocr_running", "source": "problem"}
        b64, mime = encode_image_to_base64(image_path)
        vision_messages = [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": problem if problem else "请识别图片中的数学问题"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ]
        image_description = vision_chat(vision_messages)
        wrapped_ocr = (
            '<user_uploaded_content source="image_ocr" trust="untrusted">\n'
            f"{image_description}\n"
            "</user_uploaded_content>"
        )
        if problem:
            combined_problem = f"{problem}\n\n{wrapped_ocr}"
        else:
            combined_problem = wrapped_ocr
        yield {"event": "ocr_done", "source": "problem", "text": image_description}

    if solution_image_path:
        yield {"event": "ocr_running", "source": "solution"}
        b64, mime = encode_image_to_base64(solution_image_path)
        solution_messages = [
            {"role": "system", "content": SOLUTION_VISION_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "请识别图片中的数学解答过程，保留步骤结构，为每步编号"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ]
        solution_ocr = vision_chat(solution_messages, temperature=0.1, max_tokens=2048)
        wrapped_solution_ocr = (
            '<user_uploaded_content source="solution_image_ocr" trust="untrusted">\n'
            f"{solution_ocr}\n"
            "</user_uploaded_content>"
        )
        if student_solution:
            wrapped_student = (
                '<user_uploaded_content source="student_text" trust="untrusted">\n'
                f"{student_solution}\n"
                "</user_uploaded_content>"
            )
            combined_solution = f"{wrapped_student}\n\n{wrapped_solution_ocr}"
        else:
            combined_solution = wrapped_solution_ocr
        yield {"event": "ocr_done", "source": "solution", "text": solution_ocr}

    difficulty = estimate_difficulty(combined_problem)
    review_cfg = REVIEW_CONFIG[difficulty]

    # 参考解只需"够用"作为对照，不需要完整 USC + 多轮纠错。
    # fast=True 把 max_iter 限到 3、跳过 post-verification 循环，整体成本下降 60%+。
    # 内部事件用 _drain 消费，不向外透传，避免 UI 上信息轰炸。
    yield {"event": "started", "phase": "generating_reference"}
    correct_result = _drain(solve(combined_problem, fast=True))
    standard_reference = correct_result["formatted_solution"]
    yield {"event": "reference_ready", "difficulty": difficulty}

    steps = parse_solution_steps(combined_solution)
    step_0 = combined_problem

    if not steps:
        steps = [combined_solution]

    premise_links = {}
    if review_cfg["max_iter"] >= 2:
        for i, step in enumerate(steps, 1):
            yield {"event": "premise_extracting", "step": i, "n": len(steps)}
            preceding = [f"Step 0: {step_0}"]
            for j in range(1, i):
                preceding.append(f"Step {j}: {steps[j - 1]}")
            premise_prompt = PREMISE_EXTRACTOR_PROMPT.format(
                step_0=step_0,
                preceding_steps="\n".join(preceding),
                current_step=step,
                step_index=i,
            )
            premise_response = solver_chat(
                [{"role": "user", "content": premise_prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            premise_links[i] = parse_premise_json(premise_response, i)
    else:
        for i in range(1, len(steps) + 1):
            premise_links[i] = {"step_index": i, "premises": [0], "explanations": {}}

    formatted_steps = format_steps_with_premises(steps, premise_links)
    formatted_links = format_premise_links(premise_links)

    router = get_mcp_router() if difficulty != "easy" else None
    mcp_tool_desc = ""
    if router:
        tool_infos = router.get_all_tool_descriptions_raw()
        mcp_tool_desc = format_mcp_tools_for_prompt(tool_infos)

    review_prompt = build_review_prompt(
        combined_problem, standard_reference, formatted_steps, formatted_links,
        mcp_tool_descriptions=mcp_tool_desc,
    )
    messages = [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": "请开始逐步批改"},
    ]

    review_steps_raw = []
    for i in range(1, review_cfg["max_iter"] + 1):
        yield {"event": "grading_step", "step": i, "n": review_cfg["max_iter"]}
        response = solver_chat(messages, temperature=0.2, max_tokens=4096)
        messages.append({"role": "assistant", "content": response})
        code_blocks = extract_code_blocks(response)
        tool_calls = extract_tool_calls(response)

        exec_result = None
        if code_blocks:
            all_code = "\n".join(code_blocks)
            yield {"event": "code_executing", "i": f"review_{i}", "code": all_code}
            exec_result = execute_code(all_code)
            yield {
                "event": "code_done",
                "i": f"review_{i}",
                "success": exec_result["success"],
                "output": exec_result["output"],
            }
            tool_msg = TOOL_RESULT_PROMPT.format(output=exec_result["output"])
            messages.append({"role": "user", "content": tool_msg})

        mcp_results = None
        if tool_calls and router:
            mcp_results = []
            for tc in tool_calls:
                yield {
                    "event": "mcp_calling",
                    "i": f"review_{i}",
                    "tool": tc["name"],
                    "args": tc["arguments"],
                }
                mcp_result = router.call_tool_sync(tc["name"], tc["arguments"])
                yield {"event": "mcp_done", "i": f"review_{i}", "tool": tc["name"], "result": mcp_result}
                mcp_results.append({"name": tc["name"], "arguments": tc["arguments"], "result": mcp_result})
                mcp_msg = MCP_TOOL_RESULT_PROMPT.format(
                    tool_result=f"Tool '{tc['name']}' called with: {json.dumps(tc['arguments'], ensure_ascii=False)}\nResult:\n{mcp_result}"
                )
                messages.append({"role": "user", "content": mcp_msg})

        review_steps_raw.append(format_iteration(i, response, exec_result, mcp_results))
        yield {"event": "step_done", "i": f"review_{i}", "content": review_steps_raw[-1]}

        if not code_blocks and not tool_calls:
            break

    grading_result = "\n\n".join(review_steps_raw)

    native_errors = extract_native_errors(grading_result)
    accumulation_errors = detect_accumulation_errors(premise_links, native_errors)

    should_meta = review_cfg["meta_check"] == True
    if review_cfg["meta_check"] == "conditional":
        should_meta = any(v is not None for v in native_errors.values())

    meta_result = ""
    if should_meta:
        yield {"event": "meta_checking"}
        meta_prompt = build_metacheck_prompt(
            problem=combined_problem,
            student_solution=combined_solution,
            grading_result=grading_result,
        )
        meta_result = solver_chat(
            [{"role": "system", "content": meta_prompt},
             {"role": "user", "content": "请审查批改结果是否有幻觉错误"}],
            temperature=0.1,
            max_tokens=2048,
        )
    else:
        meta_result = "### Meta-Verification Skipped (easy/medium problem, no errors detected)"

    formatted = format_review(
        grading_result,
        accumulation_errors,
        meta_result,
        standard_reference,
        combined_problem,
        combined_solution,
    )

    yield {
        "event": "final",
        "result": {
            "problem": combined_problem,
            "student_solution": combined_solution,
            "standard_reference": standard_reference,
            "steps": steps,
            "premise_links": premise_links,
            "native_errors": native_errors,
            "accumulation_errors": accumulation_errors,
            "grading_result": grading_result,
            "meta_result": meta_result,
            "formatted_review": formatted,
            "ocr_problem": image_description,
            "ocr_solution": solution_ocr,
            "difficulty": difficulty,
        },
    }
