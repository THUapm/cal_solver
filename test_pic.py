"""pic/ 真实手写图片端到端测试。

覆盖：
1. 题目 OCR（手写图片 → LaTeX）
2. 解答 OCR（手写图片 → 步骤化 LaTeX）
3. review() 完整流程（批改 + 置信度 + 标准解）
4. generate_similar_problems() 举一反三

运行：
    python test_pic.py [--case all|q-a1|q-a2] [--samples N]

需要：API_KEY 配置在 .env

设计原则：
- 不写硬断言（LLM 输出非确定性）
- 中间产物保存到 pic/ 便于人工评估
- 结构化结果保存到 pic/test_results.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from src.agent import review, generate_similar_problems
from src.llm_client import vision_chat, encode_image_to_base64
from src.prompts import VISION_SYSTEM_PROMPT, SOLUTION_VISION_PROMPT
from src.utils import parse_similar_problems

PROJECT_ROOT = Path(__file__).parent
PIC_DIR = PROJECT_ROOT / "pic"

CASES = {
    "q-a1": {
        "label": "齐次 ODE x²y' + xy = y²",
        "problem_image": PIC_DIR / "Q-A1" / "Q1.jpg",
        "solution_image": PIC_DIR / "Q-A1" / "A1.jpg",
    },
    "q-a2": {
        "label": "Gronwall 引理证明",
        "problem_image": PIC_DIR / "Q-A2" / "Q2.jpg",
        "solution_image": PIC_DIR / "Q-A2" / "A2.jpg",
    },
}


def _save(name: str, content: str) -> Path:
    """保存中间产物到 pic/{name}.md（不入仓）。"""
    p = PIC_DIR / f"{name}.md"
    p.write_text(content, encoding="utf-8")
    return p


def task_ocr_problem(case: str) -> dict:
    """任务1: 题目 OCR。"""
    info = CASES[case]
    b64, mime = encode_image_to_base64(str(info["problem_image"]))
    msgs = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "请识别图片中的数学问题，用 LaTeX 写公式，保留原始题目结构"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]},
    ]
    t0 = time.time()
    text = vision_chat(msgs, temperature=0.1)
    elapsed = round(time.time() - t0, 1)
    path = _save(f"{case}_problem_ocr", text)
    return {"elapsed_sec": elapsed, "len_chars": len(text), "text": text, "saved_to": str(path)}


def task_ocr_solution(case: str) -> dict:
    """任务2: 解答 OCR。"""
    info = CASES[case]
    b64, mime = encode_image_to_base64(str(info["solution_image"]))
    msgs = [
        {"role": "system", "content": SOLUTION_VISION_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "请识别图片中的数学解答过程，保留步骤结构，为每步编号"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]},
    ]
    t0 = time.time()
    text = vision_chat(msgs, temperature=0.1, max_tokens=2048)
    elapsed = round(time.time() - t0, 1)
    path = _save(f"{case}_solution_ocr", text)
    return {"elapsed_sec": elapsed, "len_chars": len(text), "text": text, "saved_to": str(path)}


def task_review(case: str) -> dict:
    """任务3: review() 端到端批改。"""
    info = CASES[case]
    events = []
    final = None
    t0 = time.time()

    for ev in review(
        problem="",
        image_path=str(info["problem_image"]),
        student_solution="",
        solution_image_path=str(info["solution_image"]),
    ):
        events.append(ev)
        if ev.get("event") == "final":
            final = ev["result"]
            break

    elapsed = round(time.time() - t0, 1)

    event_types = [e.get("event") for e in events]
    steps_graded = [
        e for e in events if e.get("event") == "step_graded"
    ]
    review_text = (final or {}).get("formatted_review", "")
    standard_ref = (final or {}).get("standard_reference", "")
    difficulty = (final or {}).get("difficulty", "?")

    combined = (
        f"# {CASES[case]['label']} — review() 结果\n\n"
        f"**事件总数**: {len(events)}  \n"
        f"**步骤批改**: {len(steps_graded)} 步  \n"
        f"**难度**: {difficulty}  \n"
        f"**总耗时**: {elapsed}s\n\n"
        "---\n\n"
        "## 事件流（按顺序）\n\n"
        + "\n".join(f"- `{e}`" for e in event_types)
        + "\n\n---\n\n"
        "## 步骤批改详情\n\n"
        + "\n".join(
            f"- Step {s.get('step')}: confidence={s.get('confidence')}, "
            f"is_correct={s.get('is_correct')}"
            for s in steps_graded
        )
        + "\n\n---\n\n"
        "## 批改总结（formatted_review）\n\n"
        + (review_text or "_（空）_")
        + "\n\n---\n\n"
        "## 标准解法参考（standard_reference）\n\n"
        + (standard_ref or "_（空）_")
        + "\n"
    )
    path = _save(f"{case}_review", combined)

    return {
        "elapsed_sec": elapsed,
        "events_count": len(events),
        "event_types": event_types,
        "steps_graded": [
            {
                "step": s.get("step"),
                "confidence": s.get("confidence"),
                "is_correct": s.get("is_correct"),
            }
            for s in steps_graded
        ],
        "difficulty": difficulty,
        "review_text_len": len(review_text),
        "standard_ref_len": len(standard_ref),
        "saved_to": str(path),
    }


def task_similar(case: str, problem_text: str) -> dict:
    """任务4: 举一反三。"""
    t0 = time.time()
    final = None
    events = []
    for ev in generate_similar_problems(problem_text, n=3):
        events.append(ev)
        if ev.get("event") == "final":
            final = ev["result"]
            break
    elapsed = round(time.time() - t0, 1)

    if not final:
        return {"ok": False, "elapsed_sec": elapsed, "error": "no final result"}

    kp = final.get("knowledge_points", "")
    sim_text = final.get("similar_problems", "")
    problems = parse_similar_problems(sim_text)

    combined = (
        f"# {CASES[case]['label']} — 举一反三结果\n\n"
        f"**耗时**: {elapsed}s\n\n"
        "---\n\n"
        "## 知识点\n\n"
        + kp.strip()
        + "\n\n---\n\n"
        "## 相似题\n\n"
        + sim_text.strip()
        + "\n"
    )
    path = _save(f"{case}_similar", combined)

    return {
        "ok": True,
        "elapsed_sec": elapsed,
        "knowledge_points_len": len(kp),
        "similar_count": len(problems),
        "similar_titles": [p["problem"][:60] for p in problems],
        "saved_to": str(path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="all", choices=["all", "q-a1", "q-a2"])
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--skip-similar", action="store_true",
                        help="跳过举一反三（节省 token）")
    args = parser.parse_args()

    cases = list(CASES.keys()) if args.case == "all" else [args.case]
    results: dict = {"_meta": {"created": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "samples": args.samples,
                                "skip_similar": args.skip_similar}}

    for case in cases:
        print(f"\n{'=' * 60}\n  用例: {case} — {CASES[case]['label']}\n{'=' * 60}")
        results[case] = {}

        # 1. 题目 OCR
        print("\n[1/4] 题目 OCR...", flush=True)
        r = task_ocr_problem(case)
        print(f"  ✓ 耗时 {r['elapsed_sec']}s | 长度 {r['len_chars']} chars")
        print(f"  前 200 字: {r['text'][:200]}")
        results[case]["problem_ocr"] = r
        problem_text = r["text"]

        # 2. 解答 OCR
        print("\n[2/4] 解答 OCR...", flush=True)
        r = task_ocr_solution(case)
        print(f"  ✓ 耗时 {r['elapsed_sec']}s | 长度 {r['len_chars']} chars")
        print(f"  前 300 字:\n{r['text'][:300]}")
        results[case]["solution_ocr"] = r

        # 3. review()
        print("\n[3/4] review() 端到端批改...", flush=True)
        r = task_review(case)
        print(f"  ✓ 总耗时 {r['elapsed_sec']}s | 事件 {r['events_count']} | "
              f"步骤 {len(r['steps_graded'])} | 难度 {r['difficulty']}")
        print(f"  事件流: {' → '.join(r['event_types'][:6])}"
              f"{' → ...' if len(r['event_types']) > 6 else ''}")
        print(f"  步骤置信度: {[(s['step'], s['confidence'], s['is_correct']) for s in r['steps_graded']]}")
        results[case]["review"] = r

        # 4. 举一反三
        if args.skip_similar:
            print("\n[4/4] 举一反三：跳过（--skip-similar）")
            results[case]["similar"] = {"skipped": True}
        else:
            print("\n[4/4] generate_similar_problems()...", flush=True)
            r = task_similar(case, problem_text)
            if r.get("ok"):
                print(f"  ✓ 耗时 {r['elapsed_sec']}s | 相似题 {r['similar_count']} 道")
                for t in r["similar_titles"]:
                    print(f"     - {t}")
            else:
                print(f"  ✗ 失败: {r.get('error')}")
            results[case]["similar"] = r

    # 保存结构化结果
    out = PIC_DIR / "test_results.json"

    def _to_jsonable(obj):
        if isinstance(obj, dict):
            return {k: _to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_jsonable(v) for v in obj]
        if isinstance(obj, Path):
            return str(obj)
        return obj

    out.write_text(
        json.dumps(_to_jsonable(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{'=' * 60}\n✅ 结果已保存: {out}")
    print(f"   中间产物在 pic/ 下 4 × {len(cases)} = {4 * len(cases)} 个 .md 文件")


if __name__ == "__main__":
    main()
