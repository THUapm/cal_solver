import sys
sys.stdout.reconfigure(encoding='utf-8')


def test_classify_schema_keyword_match():
    from src.schemas import classify_schema

    result = classify_schema("求 f(x)=x²*e^x 的不定积分（换元积分法）")
    assert result is not None
    assert result["name"] == "u_substitution_integral"
    print(f"Schema match: {result['name']}")

    result2 = classify_schema("已知P(A)=0.3, P(B|A)=0.8, P(B)=0.5，求P(A|B)（贝叶斯定理）")
    assert result2 is not None
    assert result2["name"] == "bayes_theorem"
    print(f"Schema match: {result2['name']}")

    result3 = classify_schema("一个正态分布 N(μ=10, σ=2)，求 P(X<=12)")
    assert result3 is not None
    assert result3["category"] == "probability"
    print(f"Schema match: {result3['name']}")

    result4 = classify_schema("求 f(x) = ln(x) + x^3 在 x=1 处的导数")
    assert result4 is not None
    assert result4["category"] == "calculus"
    print(f"Schema match: {result4['name']}")


def test_classify_schema_no_match():
    from src.schemas import classify_schema

    result = classify_schema("这是一个纯文本没有数学关键词的问题")
    assert result is None
    print(f"No match: {result}")


def test_classify_schema_multiple_match():
    from src.schemas import classify_schema

    result = classify_schema("求∫sin²x cos x dx（三角积分用换元法）")
    assert result is not None
    print(f"Multiple match resolved: {result['name']} (score reflects keyword density)")


def test_estimate_difficulty():
    from src.agent import estimate_difficulty

    d1 = estimate_difficulty("求 f(x) = x^2 的导数")
    assert d1 == "easy"
    print(f"Easy: '{d1}'")

    d2 = estimate_difficulty("证明不等式：对任意正数x，ln(x) ≤ x-1")
    assert d2 == "hard"
    print(f"Hard: '{d2}'")

    d3 = estimate_difficulty("计算 ∫₀¹ x² dx")
    assert d3 in ("easy", "medium", "hard")
    print(f"Default/medium: '{d3}'")

    d4 = estimate_difficulty("抛硬币10次，恰好出现3次正面的概率是多少？")
    assert d4 in ("easy", "medium")
    print(f"Probability problem: '{d4}'")


def test_parse_verification_errors():
    from src.utils import parse_verification_errors

    pass_text = "✓ Verification passed. All steps are correct. ✓ All intermediate results verified."
    result = parse_verification_errors(pass_text)
    assert result is None
    print(f"Pass → None: {result}")

    error_text = "✗ Error in Step 2: calculation error, the derivative of e^x should be e^x not e^x*2. ✗ This step does not follow from premises."
    result = parse_verification_errors(error_text)
    assert result is not None
    assert "✗" in result or "Error" in result
    print(f"Error found: {result[:80]}...")

    mixed_text = "Step 1: ✓ correct. Step 2: ✗ wrong computation."
    result = parse_verification_errors(mixed_text)
    assert result is not None
    print(f"Mixed → error found: {result[:80]}...")


def test_extract_final_answer_value():
    from src.utils import extract_final_answer_value

    a1 = extract_final_answer_value("$$\\boxed{42}$$")
    assert a1 == "42"
    print(f"Boxed: {a1}")

    a2 = extract_final_answer_value("最终答案：3x² + C")
    assert a2 == "3x² + C"
    print(f"Chinese answer: {a2}")

    a3 = extract_final_answer_value("The answer is: 0.8413")
    assert a3 == "0.8413"
    print(f"English answer: {a3}")

    a4 = extract_final_answer_value("No answer here")
    assert a4 is None
    print(f"No answer: {a4}")


def test_all_answers_agree():
    from src.utils import all_answers_agree

    assert all_answers_agree(["42", "42", "42"]) == True
    print("Consistent answers: agree")

    assert all_answers_agree(["42", "43", "42"]) == False
    print("Divergent answers: disagree")

    assert all_answers_agree(["0.8413", "0.84134", "0.8413"]) == True
    print("Numerical close: agree")

    assert all_answers_agree([None, "42"]) == True
    print("With None: agree (only 1 valid)")

    assert all_answers_agree(["42", None, "42"]) == True
    print("Mixed None: agree")


def test_parse_usc_selection():
    from src.utils import parse_usc_selection

    json_text = "```json\n{\"selected\": 2, \"reason\": \"most consistent\"}\n```"
    result = parse_usc_selection(json_text)
    assert result == 2
    print(f"JSON selection: {result}")

    text_selection = "I choose solution 1 because it has the most thorough verification."
    result = parse_usc_selection(text_selection)
    assert result == 1
    print(f"Text selection: {result}")

    fallback_text = "The second path seems best."
    result = parse_usc_selection(fallback_text)
    print(f"Fallback selection: {result}")


def test_difficulty_config_routing():
    from src.agent import DIFFICULTY_CONFIG, REVIEW_CONFIG

    for level in ("easy", "medium", "hard"):
        assert level in DIFFICULTY_CONFIG
        cfg = DIFFICULTY_CONFIG[level]
        assert "max_iter" in cfg
        assert "use_mcp" in cfg
        assert "use_self_consistency" in cfg
        print(f"DIFFICULTY_CONFIG[{level}]: {cfg}")

    for level in ("easy", "medium", "hard"):
        assert level in REVIEW_CONFIG
        cfg = REVIEW_CONFIG[level]
        assert "max_iter" in cfg
        assert "meta_check" in cfg
        print(f"REVIEW_CONFIG[{level}]: {cfg}")


def test_schema_injection_format():
    from src.schemas import classify_schema, format_schema_injection_text

    schema_info = classify_schema("求 f(x)=x²*e^x 的不定积分换元")
    assert schema_info is not None
    formatted = format_schema_injection_text(schema_info)
    assert "Problem Schema" in formatted
    assert schema_info["name"] in formatted
    assert "Recommended step sequence" in formatted
    assert "Common pitfalls" in formatted
    print(f"Schema injection format OK (length: {len(formatted)} chars)")
    print(f"First 200 chars: {formatted[:200]}...")


def test_build_solver_prompt_with_skills():
    from src.prompts import build_solver_prompt_with_skills
    from src.schemas import classify_schema, format_schema_injection_text

    schema_info = classify_schema("求 f(x)=x²*e^x 的不定积分换元")
    schema_text = format_schema_injection_text(schema_info) if schema_info else ""

    prompt = build_solver_prompt_with_skills(
        mcp_tool_descriptions="",
        schema_info=schema_text,
        verify_first=True,
    )
    assert "Verify-First" in prompt
    assert "Proactive Cross-Verification" in prompt
    assert "Problem Schema" in prompt
    assert "u_substitution_integral" in prompt
    print(f"Enhanced solver prompt OK (length: {len(prompt)} chars)")

    prompt_no_verify = build_solver_prompt_with_skills(
        mcp_tool_descriptions="",
        schema_info="",
        verify_first=False,
    )
    assert "Verify-First" not in prompt_no_verify
    print(f"Prompt without skills OK (length: {len(prompt_no_verify)} chars)")


def test_probability_few_shot_in_solver_prompt():
    """验证 PROBABILITY_FEW_SHOT 被注入到 solver prompt，包含全部 10 道题关键词。"""
    from src.prompts import build_solver_prompt_with_skills, PROBABILITY_FEW_SHOT

    assert len(PROBABILITY_FEW_SHOT) > 2000, \
        f"PROBABILITY_FEW_SHOT too short: {len(PROBABILITY_FEW_SHOT)} chars"

    prompt = build_solver_prompt_with_skills()
    assert "PROBABILITY_FEW_SHOT" not in prompt  # 不应泄漏常量名
    assert "Example 1" in prompt and "Example 10" in prompt

    # 10 道题的核心概念关键词必须全部出现
    required_keywords = [
        "正态分布",          # Ex1
        "MLE", "Fisher",    # Ex2
        "顺序统计量",        # Ex3
        "矩母函数", "M_X",   # Ex4
        "Z =", "H₀", "拒绝",  # Ex5
        "贝叶斯", "后验", "先验",  # Ex6
        "t_{α/2", "置信区间",  # Ex7
        "充分统计量", "因子分解",  # Ex8
        "大数定律", "Chebyshev", "中心极限定理",  # Ex9
        "Jacobian", "det",  # Ex10
    ]
    missing = [k for k in required_keywords if k not in prompt]
    assert not missing, f"Missing keywords in solver prompt: {missing}"
    print(f"PROBABILITY_FEW_SHOT OK ({len(PROBABILITY_FEW_SHOT)} chars, all 10 examples + keywords present)")


def test_few_shot_format_template():
    """抽样 1 道题，验证遵循 STRICT 模板（题目/解题/代码/验证/答案 五段）。"""
    from src.prompts import PROBABILITY_FEW_SHOT

    required_markers = [
        "**题目**",
        "**解题**",
        "```python",
        "**验证**",
        "$$",
        "\\boxed",
    ]
    missing = [m for m in required_markers if m not in PROBABILITY_FEW_SHOT]
    assert not missing, f"PROBABILITY_FEW_SHOT 缺少模板标记: {missing}"

    # 每道题都应有这 5 段，统计 *题目* 出现次数应 = 10
    count = PROBABILITY_FEW_SHOT.count("**题目**")
    assert count == 10, f"应有 10 道题，但找到 {count} 个 '**题目**' 标记"
    print(f"Template format OK: 10 examples, all with 题目/解题/代码/验证/答案")


def test_few_shot_can_be_disabled():
    """include_few_shot=False 时不注入 few-shot（向后兼容）。"""
    from src.prompts import build_solver_prompt_with_skills

    p_on = build_solver_prompt_with_skills(include_few_shot=True)
    p_off = build_solver_prompt_with_skills(include_few_shot=False)

    assert "Example 1" in p_on
    assert "Example 1" not in p_off
    # UNTRUSTED guard 必须在两种情况下都存在
    assert "user_uploaded_content" in p_on
    assert "user_uploaded_content" in p_off
    print(f"include_few_shot toggle OK: on={len(p_on)} chars, off={len(p_off)} chars")


def test_new_inference_schemas_classify():
    """验证 5 个新加的概率/统计推断 schema 都能被分类命中。"""
    from src.schemas import classify_schema

    cases = [
        ("求 lambda 的最大似然估计", "mle_estimation"),
        ("证明 T 是充分统计量", "sufficient_statistic"),
        ("原假设 H0: mu=100, n=25, 求拒绝域", "hypothesis_testing"),
        ("求 mu 的 95% 置信区间", "confidence_interval"),
        ("设先验 P(theta=1)=0.5, 观测 X=1.5, 求后验", "bayesian_inference"),
        ("Z 检验某产品寿命", "hypothesis_testing"),
        ("t 区间估计", "confidence_interval"),
    ]
    for prob, expected in cases:
        result = classify_schema(prob)
        actual = result["name"] if result else None
        assert actual == expected, \
            f"classify_schema({prob!r}) expected={expected}, got={actual}"
    print(f"5 new inference schemas: {len(cases)} classification cases all OK")


if __name__ == "__main__":
    test_classify_schema_keyword_match()
    test_classify_schema_no_match()
    test_classify_schema_multiple_match()
    test_estimate_difficulty()
    test_parse_verification_errors()
    test_extract_final_answer_value()
    test_all_answers_agree()
    test_parse_usc_selection()
    test_difficulty_config_routing()
    test_schema_injection_format()
    test_build_solver_prompt_with_skills()
    test_probability_few_shot_in_solver_prompt()
    test_few_shot_format_template()
    test_few_shot_can_be_disabled()
    test_new_inference_schemas_classify()
    print("\n✅ All skill tests passed!")