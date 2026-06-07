from src.prompts import build_schema_injection

MATH_SCHEMES = [
    {
        "name": "u_substitution_integral",
        "keywords": ["换元积分", "不定积分换元", "u-substitution", "复合函数积分", "∫", "换元", "令u=", "令t="],
        "category": "calculus",
        "step_template": "1. Identify inner function u = g(x) and compute du = g'(x)dx\n2. Rewrite the integral entirely in terms of u and du\n3. Evaluate the simpler integral with respect to u\n4. Substitute back x = g⁻¹(u) to express result in original variable\n5. Add +C for indefinite integrals",
        "common_pitfalls": [
            "forgetting to compute du (missing g'(x)dx substitution)",
            "substituting in wrong direction (replacing x when should replace entire expression)",
            "forgetting +C for indefinite integrals",
            "choosing a u that makes the new integral harder, not easier",
        ],
        "verification": "differentiate the result — d/dx[F(x)] must equal the original integrand f(x)",
    },
    {
        "name": "integration_by_parts",
        "keywords": ["分部积分", "integration by parts", "∫u dv", "LIATE", "乘积积分", "x*exp", "x*sin", "x*cos", "x*ln", "ln(x)*x", "arctan*x", "e^x*sin"],
        "category": "calculus",
        "step_template": "1. Choose u and dv using the LIATE priority rule (Log, Inv trig, Algebraic, Trig, Exp)\n2. Compute du = u'dx and v = ∫dv\n3. Apply formula ∫u dv = uv - ∫v du\n4. Solve the remaining ∫v du integral\n5. Simplify and add +C for indefinite integrals",
        "common_pitfalls": [
            "choosing u/dv incorrectly (LIATE rule violated)",
            "forgetting to integrate dv to get v before applying formula",
            "remaining integral ∫v du is harder than the original",
            "applying IBP multiple times without cycling back to original",
        ],
        "verification": "differentiate the result to recover original integrand; for definite integrals, check boundary values",
    },
    {
        "name": "definite_integral",
        "keywords": ["定积分", "definite integral", "∫_0", "∫_{", "积分区间", "面积", "上下限", "from a to b"],
        "category": "calculus",
        "step_template": "1. Find the antiderivative F(x) using appropriate method (substitution, IBP, etc.)\n2. Evaluate F(b) - F(a) by substituting upper and lower bounds\n3. Simplify the numerical/symbolic result\n4. For area problems: verify sign and interpret geometrically",
        "common_pitfalls": [
            "forgetting to substitute bounds (leaving answer as antiderivative + C)",
            "sign errors when integrand is negative over interval",
            "incorrect bounds interpretation (reversed a and b)",
            "adding +C to definite integral results (should be F(b)-F(a), no +C)",
        ],
        "verification": "numerical check: compute integral via scipy and compare; for simple integrals, verify by differentiating F(x)",
    },
    {
        "name": "trig_integral",
        "keywords": ["三角积分", "trigonometric integral", "∫sin", "∫cos", "∫tan", "∫sec", "sin^2", "cos^2", "三角恒等式", "半角公式", "倍角公式"],
        "category": "calculus",
        "step_template": "1. Identify the trig function pattern (sin^n, cos^n, sin*cos, etc.)\n2. Apply appropriate trig identity (sin²+cos²=1, double-angle, half-angle)\n3. Rewrite integral in simpler form using the identity\n4. Integrate the simplified expression\n5. Convert back to original trig variable if needed",
        "common_pitfalls": [
            "using wrong trig identity for the power pattern",
            "forgetting the sin²x+cos²x=1 reduction for odd/even powers",
            "incorrectly applying double-angle formulas",
            "mixing up which substitution to use for ∫sin^n x cos^m x dx",
        ],
        "verification": "differentiate result; numerical substitution at known points (e.g., x=0, π/4, π/2)",
    },
    {
        "name": "limit_computation",
        "keywords": ["极限", "limit", "lim", "趋近", "→0", "→∞", "→a", "连续性", "左右极限"],
        "category": "calculus",
        "step_template": "1. Identify the point of approach and check if direct substitution works\n2. If direct substitution gives 0/0 or ∞/∞ → apply limit technique\n3. Choose technique: algebraic simplification, L'Hôpital, series expansion, squeeze theorem\n4. Compute the limit using the chosen technique\n5. Check one-sided limits if needed (limit from left and right)",
        "common_pitfalls": [
            "applying L'Hôpital when conditions are not met (not 0/0 or ∞/∞ form)",
            "forgetting to check one-sided limits for piecewise functions",
            "circular reasoning with L'Hôpital (differentiating requires knowing the limit)",
            "incorrect series expansion truncation",
        ],
        "verification": "numerical check: evaluate function at points approaching the limit; symbolic check with SymPy limit()",
    },
    {
        "name": "limit_lhopital",
        "keywords": ["洛必达", "L'Hôpital", "L'Hopital", "0/0型", "∞/∞型", "未定式", "indeterminate"],
        "category": "calculus",
        "step_template": "1. Verify the limit is in 0/0 or ∞/∞ indeterminate form\n2. Differentiate numerator and denominator separately\n3. Evaluate the new limit (may need to apply L'Hôpital again)\n4. Repeat if still indeterminate (but watch for circularity)\n5. State final limit value",
        "common_pitfalls": [
            "applying L'Hôpital when limit is NOT indeterminate",
            "differentiating the entire fraction instead of numerator and denominator separately",
            "infinite L'Hôpital cycles without convergence",
            "forgetting to re-check indeterminate form after each application",
        ],
        "verification": "compute numerically near the limit point; use SymPy limit() as cross-check",
    },
    {
        "name": "derivative_computation",
        "keywords": ["导数", "derivative", "f'(x)", "求导", "微分", "变化率", "切线斜率", "dy/dx"],
        "category": "calculus",
        "step_template": "1. Identify the function and the differentiation variable\n2. Choose appropriate rule: power, product, quotient, chain\n3. Apply the rule step by step, simplifying intermediate results\n4. Write the final derivative in simplified form\n5. Evaluate at specific point if required",
        "common_pitfalls": [
            "forgetting chain rule for composite functions",
            "wrong quotient rule order (should be (vu'-uv')/v²)",
            "not simplifying intermediate results leading to errors",
            "missing negative signs from differentiation",
        ],
        "verification": "numerical check: compute derivative at a point via SymPy; check derivative satisfies basic properties",
    },
    {
        "name": "higher_derivative",
        "keywords": ["二阶导数", "高阶导数", "f''(x)", "second derivative", "n阶导数", "n-th derivative", "凹凸性", "拐点"],
        "category": "calculus",
        "step_template": "1. Compute first derivative f'(x)\n2. Differentiate f'(x) to get f''(x)\n3. Continue for n-th derivative if needed\n4. Simplify at each stage to avoid expression explosion\n5. Evaluate at specific point if required",
        "common_pitfalls": [
            "compounding errors from first derivative mistakes",
            "expression explosion without simplification between steps",
            "wrong pattern identification for n-th derivative formulas",
            "forgetting to simplify before each differentiation step",
        ],
        "verification": "check first derivative separately; numerical evaluation at multiple points",
    },
    {
        "name": "partial_derivative",
        "keywords": ["偏导数", "partial derivative", "∂f/∂x", "∂f/∂y", "多元函数", "梯度", "multivariable"],
        "category": "calculus",
        "step_template": "1. Identify the function f(x,y,...) and the variable to differentiate against\n2. Treat all other variables as constants\n3. Apply standard differentiation rules to the chosen variable\n4. Simplify the partial derivative result\n5. Compute gradient or higher partials if needed",
        "common_pitfalls": [
            "forgetting to treat other variables as constants",
            "mixing up which variable is held constant",
            "wrong mixed partial order (∂²f/∂x∂y vs ∂²f/∂y∂x)",
        ],
        "verification": "numerical check at specific point; Clairaut's theorem for mixed partials",
    },
    {
        "name": "taylor_series",
        "keywords": ["泰勒展开", "Taylor series", "麦克劳林", "Maclaurin", "级数展开", "近似", "n阶展开", "截断误差"],
        "category": "calculus",
        "step_template": "1. Identify expansion point a (Maclaurin if a=0) and order n\n2. Compute derivatives f'(a), f''(a), ..., f^(n)(a)\n3. Construct Taylor polynomial: Σ f^(k)(a)/k! * (x-a)^k\n4. Simplify the series expression\n5. Estimate truncation error using remainder term if needed",
        "common_pitfalls": [
            "wrong derivative computation at expansion point",
            "forgetting factorial denominators (k!)",
            "incorrect (x-a)^k powers",
            "not evaluating derivatives at the correct point a",
        ],
        "verification": "compare Taylor approximation to actual function value at nearby points; check limit behavior",
    },
    {
        "name": "equation_solving",
        "keywords": ["解方程", "solve equation", "求根", "roots", "零点", "x="],
        "category": "calculus",
        "step_template": "1. Write equation in standard form f(x) = 0\n2. Identify equation type (linear, quadratic, polynomial, transcendental)\n3. Choose solving method (factoring, quadratic formula, Newton's method, SymPy solve)\n4. Find all solutions (real and complex if needed)\n5. Verify each solution by substitution",
        "common_pitfalls": [
            "missing solutions (especially negative or complex roots)",
            "incorrect quadratic formula application",
            "dividing by variable expressions that could be zero",
            "extraneous solutions from squaring both sides",
        ],
        "verification": "substitute each found solution back into original equation; numerical verification",
    },
    {
        "name": "optimization_max_min",
        "keywords": ["极值", "极大值", "极小值", "最大值", "最小值", "maximum", "minimum", "极值点", "最值", "优化", "驻点", "critical point"],
        "category": "calculus",
        "step_template": "1. Find f'(x) and set it equal to zero to find critical points\n2. Solve f'(x) = 0 for critical values\n3. Evaluate f''(x) at each critical point (f''>0 → min, f''<0 → max)\n4. Check boundary values if domain is restricted\n5. Compare all candidates to determine global max/min",
        "common_pitfalls": [
            "forgetting to check boundary values on closed intervals",
            "confusing local and global extrema",
            "wrong second derivative test interpretation",
            "not checking endpoints for constrained problems",
        ],
        "verification": "compare function values at all critical points and boundaries; numerical grid search for confirmation",
    },
    {
        "name": "bayes_theorem",
        "keywords": ["贝叶斯", "Bayes", "条件概率", "P(A|B)", "后验概率", "先验概率", "P(B|A)", "逆概率"],
        "category": "probability",
        "step_template": "1. Identify P(A), P(B), P(B|A) from the problem statement\n2. Compute P(A∩B) = P(A) * P(B|A)\n3. Compute P(A|B) = P(A∩B) / P(B) = P(A)*P(B|A) / P(B)\n4. Simplify the result\n5. Verify: P(A|B) must be in [0,1]; check consistency with P(A) and P(B)",
        "common_pitfalls": [
            "confusing P(A|B) with P(B|A) (the most common error)",
            "incorrect P(B) computation (forgetting total probability law)",
            "wrong numerator: using P(B)*P(A|B) instead of P(A)*P(B|A)",
            "not verifying result is in [0,1]",
        ],
        "verification": "check result ∈ [0,1]; verify P(A|B)*P(B) = P(A)*P(B|A); numerical cross-check with scipy",
    },
    {
        "name": "binomial_distribution",
        "keywords": ["二项分布", "binomial", "Bin(n,p)", "抛硬币", "成功次数", "C(n,k)*p^k", "独立重复试验", "伯努利"],
        "category": "probability",
        "step_template": "1. Identify n (number of trials), p (success probability), k (target count)\n2. Compute P(X=k) = C(n,k) * p^k * (1-p)^(n-k)\n3. Compute C(n,k) = comb(n, k) carefully\n4. For cumulative: sum P(X≤k) = Σ P(X=i) for i=0 to k\n5. Verify: P(X=k) ∈ [0,1], ΣP(X=k)=1 for all k",
        "common_pitfalls": [
            "wrong C(n,k) computation (confusing with P(n,k))",
            "forgetting (1-p)^(n-k) factor",
            "mixing up k and n-k in the formula",
            "not recognizing binomial setup from problem description",
        ],
        "verification": "verify sum of all P(X=k) equals 1; use scipy.stats.binom for numerical cross-check",
    },
    {
        "name": "normal_distribution",
        "keywords": ["正态分布", "normal distribution", "N(μ,σ)", "高斯分布", "Gaussian", "标准化", "Z-score", "P(X≤)", "标准正态"],
        "category": "probability",
        "step_template": "1. Identify μ (mean) and σ (standard deviation)\n2. Standardize: Z = (X - μ) / σ\n3. Find P(X ≤ x) = P(Z ≤ (x-μ)/σ) using standard normal table or scipy\n4. For interval probability: P(a ≤ X ≤ b) = P(Z ≤ (b-μ)/σ) - P(Z ≤ (a-μ)/σ)\n5. Verify: result ∈ [0,1]; check monotonicity of CDF",
        "common_pitfalls": [
            "confusing σ (std) with σ² (variance) in the formula",
            "wrong Z-score direction (sign error)",
            "forgetting to use σ not σ² in standardization",
            "incorrect table lookup or scipy parameter order (loc=μ, scale=σ)",
        ],
        "verification": "verify result ∈ [0,1]; use scipy.stats.norm.cdf as cross-check; check symmetry properties",
    },
    {
        "name": "poisson_distribution",
        "keywords": ["泊松分布", "Poisson", "λ", "稀有事件", "e^(-λ)", "P(X=k)", "平均发生率"],
        "category": "probability",
        "step_template": "1. Identify λ (average rate/mean)\n2. Compute P(X=k) = e^(-λ) * λ^k / k!\n3. For cumulative: P(X≤k) = Σ P(X=i) for i=0 to k\n4. Simplify numerical result\n5. Verify: P(X=k) ∈ [0,1]; E[X] = λ, Var[X] = λ",
        "common_pitfalls": [
            "wrong λ identification from problem",
            "forgetting factorial denominator k!",
            "confusing P(X=k) with P(X≤k)",
            "incorrect e^(-λ) computation",
        ],
        "verification": "verify ΣP(X=k) ≈ 1 for reasonable k range; use scipy.stats.poisson; check E[X]=Var[X]=λ",
    },
    {
        "name": "combinatorics_counting",
        "keywords": ["组合", "排列", "C(n,k)", "P(n,k)", "组合数", "排列数", "不放回", "取球", "抽取", "组合计数", "comb", "perm"],
        "category": "probability",
        "step_template": "1. Identify total number of items n and selection size k\n2. Determine: order matters (permutation P(n,k)) or not (combination C(n,k))\n3. Determine: with replacement or without\n4. Compute the count using appropriate formula\n5. Divide by total outcomes for probability if needed",
        "common_pitfalls": [
            "confusing combination and permutation (order relevance)",
            "not accounting for with/without replacement correctly",
            "incorrect C(n,k) = n!/(k!(n-k)!) formula",
            "missing cases in multi-category problems (red+white+black balls)",
        ],
        "verification": "check that probability ∈ [0,1]; enumerate small cases manually; use math.comb/math.perm for cross-check",
    },
    {
        "name": "conditional_probability",
        "keywords": ["条件概率", "P(A|B)", "已知B发生", "在条件下", "交集概率", "P(A∩B)", "独立性检验"],
        "category": "probability",
        "step_template": "1. Identify events A and B and the conditioning event\n2. Compute P(A∩B) using given information\n3. Compute P(B) (the conditioning event's probability)\n4. Apply P(A|B) = P(A∩B) / P(B)\n5. Check independence: A and B independent iff P(A|B) = P(A)",
        "common_pitfalls": [
            "dividing by P(B) = 0 (conditioning on impossible event)",
            "confusing P(A|B) with P(A∩B)",
            "incorrect P(A∩B) from multiplication rule",
            "not checking independence when it matters",
        ],
        "verification": "verify P(A|B) ∈ [0,1]; check P(A|B)*P(B) = P(A∩B); verify P(B) > 0",
    },
    {
        "name": "expectation_variance",
        "keywords": ["期望", "方差", "E[X]", "Var[X]", "均值", "标准差", "E(X)", "V(X)", "数学期望"],
        "category": "probability",
        "step_template": "1. Identify the distribution and its parameters\n2. Compute E[X] using definition or known formula\n3. Compute Var[X] = E[X²] - (E[X])² or known formula\n4. Compute std = √Var[X] if needed\n5. Verify: Var[X] ≥ 0; results consistent with distribution properties",
        "common_pitfalls": [
            "confusing Var[X] = E[X²] - E[X]² with Var[X] = E[(X-E[X])²]",
            "wrong formula for specific distribution (e.g., Binom Var = np(1-p), not np)",
            "forgetting (E[X])² term in variance computation",
            "incorrect E[X²] computation",
        ],
        "verification": "check Var[X] ≥ 0; compare with known distribution formulas; numerical verification via scipy",
    },
    {
        "name": "continuous_distribution",
        "keywords": ["连续分布", "CDF", "PDF", "概率密度", "分布函数", "累积分布", "概率密度函数", "均匀分布", "指数分布", "P(X≤x)", "P(X>x)", "P(a<X<b)"],
        "category": "probability",
        "step_template": "1. Identify the distribution type and parameters\n2. Use PDF f(x) for point probability density or CDF F(x) for cumulative probability\n3. Compute the requested quantity (P(X≤x), P(X>x), P(a<X<b))\n4. For quantile problems: use inverse CDF (ppf)\n5. Verify: CDF is monotonically increasing from 0 to 1; PDF integrates to 1",
        "common_pitfalls": [
            "confusing PDF value with probability (PDF ≠ P for continuous distributions)",
            "wrong parameterization (loc/scale vs raw parameters)",
            "forgetting that P(X=x) = 0 for continuous distributions",
            "incorrect interval probability computation",
        ],
        "verification": "verify CDF ∈ [0,1] and monotonic; check PDF integral = 1; use scipy.stats for numerical cross-check",
    },
    {
        "name": "mle_estimation",
        "keywords": ["最大似然估计", "MLE", "似然函数", "对数似然", "Fisher 信息", "FISHER", "极大似然", "似然估计", "score function", "score 方程", "参数估计"],
        "category": "probability",
        "step_template": "1. 写出联合密度 L(θ) = ∏ f(xᵢ|θ)\n2. 取对数似然 ℓ(θ) = ln L(θ)\n3. 求 ∂ℓ/∂θ = 0（解 MLE 方程）\n4. 验证二阶条件 ∂²ℓ/∂θ² < 0 确认极大值\n5. 若问 Fisher 信息：I(θ) = -E[∂²ℓ/∂θ²]\n6. 若问渐近正态：√n(θ̂−θ) → N(0, 1/I(θ))",
        "common_pitfalls": [
            "对数似然取 ln 后忘记乘以 n（独立同分布）",
            "求导时变量记错（参数 vs 样本均值）",
            "Fisher 信息写反：是 -E[∂²ℓ/∂θ²]，不是 E[(∂ℓ/∂θ)²]（后者是 CRLB 下界）",
            "MLE 有偏时不修正（如 Exp 的 1/X̄ 有偏需 n/(n−1) 修正）",
            "对含约束参数（如 σ²>0）取负值时忘记拉格朗日乘子",
        ],
        "verification": "代入数值样本验证 MLE 方程=0；用 sympy 求二阶导确认负；用 Fisher 信息计算 CRLB 并与无偏估计方差比较",
    },
    {
        "name": "sufficient_statistic",
        "keywords": ["充分统计量", "因子分解定理", "Fisher-Neyman", "充分性", "最小充分", "完备统计量", "Basu 定理", "sufficiency", "factorization"],
        "category": "probability",
        "step_template": "1. 写出联合密度 f(x₁,...,xₙ|θ)\n2. 尝试因子分解为 g(T(x)|θ) · h(x)\n3. 若 h(x) 与 θ 无关 → T 是充分统计量\n4. 若 T 与其他所有充分统计量一一对应 → T 是最小充分统计量\n5. 若 E[g(T)] = 0 对所有 θ ⟹ g(T)=0 a.s. → T 完备\n6. 完备 + 充分 → 最小充分 = 完全充分",
        "common_pitfalls": [
            "因子分解时把 θ 留在 h(x) 里（h 必须与 θ 无关）",
            "充分统计量不一定唯一（X̄ 和 ΣXᵢ 对正态 N(μ,σ²) 都是充分的）",
            "最小充分统计量需要先验证 T 是充分，再验证一一对应",
            "漏掉符号：X̄ 是充分统计量但 Σ(Xᵢ−X̄)² 是 σ² 的充分统计量",
        ],
        "verification": "用 sympy 化简联合密度 − g(T)·h(x) 验证 ≡ 0；用因子分解定理反例（指数族可分）确认无遗漏",
    },
    {
        "name": "hypothesis_testing",
        "keywords": ["假设检验", "Z 检验", "t 检验", "卡方检验", "F 检验", "显著性检验", "p-value", "p 值", "拒绝域", "H0", "H₁", "H_0", "H_1", "原假设", "备择假设", "显著性水平", "α=", "α =", "第一类错误", "第二类错误", "功效函数", "Neyman-Pearson", "似然比检验", "LR test"],
        "category": "probability",
        "step_template": "1. 陈述 H₀ 与 H₁（注意单/双侧）\n2. 选检验统计量：Z / t / χ² / F / LRT\n3. 计算检验统计量的观测值\n4. 查表或用 scipy 求临界值或 p-value\n5. 比较：|统计量| > 临界值 或 p < α → 拒绝 H₀\n6. 报告结论（不要写'接受 H₀'，写'不拒绝 H₀'）",
        "common_pitfalls": [
            "σ² 已知时用 Z，未知时用 t 分布（用错方差是常见错误）",
            "单侧检验的拒绝域在一侧而非两侧",
            "p-value 不是 H₀ 为真的概率，是'在 H₀ 成立时观测到该样本或更极端'的概率",
            "样本量小时（n<30）正态总体也应优先用 t",
            "配对样本用配对 t 而非两组独立 t",
        ],
        "verification": "用 scipy.stats 计算 p-value 验证手算；用功效函数 power 分析样本量是否足够；Type I 错误率 = α 通过模拟验证",
    },
    {
        "name": "confidence_interval",
        "keywords": ["置信区间", "置信水平", "1-α", "枢轴量", "pivot", "t 区间", "z 区间", "大样本区间", "Wald 区间", "Wilson 区间", "CI", "confidence interval"],
        "category": "probability",
        "step_template": "1. 找枢轴量 Q(X, θ) 使其分布不含未知参数\n2. P(a < Q < b) = 1 − α，找 a, b 使 P = 1−α\n3. 反解不等式得 θ 的区间 (L(X), U(X))\n4. 单参数时常用 Z / t / χ² / F 分布；多参数时用联合枢轴\n5. 解释：重复抽样下，约 (1−α)% 的区间包含真值",
        "common_pitfalls": [
            "σ² 未知时不能直接用 Z 区间（必须用 t 区间）",
            "比例 p 的置信区间 n 小时（np<5）正态近似不准，用 Wilson 或 Clopper-Pearson",
            "解释错误：'真值有 95% 概率落入该区间'——错误，应是'重复抽样 95% 的区间包含真值'",
            "双侧等尾未必最优（最高密度区间 HDI 更准）",
            "方差未知且 n 小时，必须用 S² 估计的 t 区间",
        ],
        "verification": "bootstrap 重抽样 1000 次，看 CI 覆盖率是否接近 1−α；n 充分大时 t → z 验证渐近",
    },
    {
        "name": "bayesian_inference",
        "keywords": ["贝叶斯推断", "贝叶斯", "先验", "后验", "似然", "先验分布", "后验分布", "共轭先验", "Beta 先验", "Dirichlet", "MAP", "贝叶斯估计", "posterior", "prior", "likelihood", "Bayes", "贝叶斯公式", "贝叶斯更新"],
        "category": "probability",
        "step_template": "1. 陈述先验 π(θ) 与似然 L(θ|x) = f(x|θ)\n2. 用 Bayes 公式：π(θ|x) ∝ π(θ) · f(x|θ)\n3. 归一化：分母 m(x) = ∫ π(θ)f(x|θ)dθ\n4. 报告后验：π(θ|x) = π(θ)f(x|θ) / m(x)\n5. 贝叶斯估计：θ̂_Bayes = E[θ|x]（后验均值）\n6. MAP：θ̂_MAP = argmax π(θ|x)\n7. 可信区间（credible interval）= 最高密度区间 HDI",
        "common_pitfalls": [
            "后验不是先验×似然直接除，要归一化（除以 m(x)）",
            "先验要选共轭先验才得到解析后验，否则需 MCMC",
            "Bernoulli 似然 + Beta 先验 → Beta 后验；高斯似然 + 高斯先验 → 高斯后验",
            "MAP ≠ 后验均值（除非后验对称）",
            "贝叶斯可信区间 (credible) ≠ 频率置信区间 (confidence)，意义完全不同",
        ],
        "verification": "验证后验归一化（∫π(θ|x)dθ = 1）；检查 MAP 与后验众数一致；用 MCMC（PyMC / emcee）数值验证解析后验",
    },
]


def classify_schema(problem: str) -> dict | None:
    best_schema = None
    best_score = 0
    problem_lower = problem.lower()
    for schema in MATH_SCHEMES:
        score = 0
        for kw in schema["keywords"]:
            if kw.lower() in problem_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_schema = schema
    if best_score >= 1 and best_schema is not None:
        return best_schema
    return None


def format_schema_injection_text(schema_info: dict) -> str:
    return build_schema_injection(schema_info)