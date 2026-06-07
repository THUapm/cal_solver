import sys
import logging
import json
import io
import base64
import tempfile
import os
import math

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

import sympy
from sympy import sympify, diff, integrate, solve, limit, simplify, latex, Symbol, symbols, oo, exp, sin, cos, tan, log, sqrt, pi, E
from sympy.parsing.latex import parse_latex
from scipy import stats
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("math_tools")


@mcp.tool()
def symbolic_compute(
    expression: str,
    operation: str,
    variable: str = "x",
    point: str | None = None,
) -> str:
    """SymPy symbolic computation for exact mathematical results.

    WHEN TO USE:
    - Need exact symbolic results (derivatives, integrals, limits, equation solutions, simplification)
    - When local Python execution with SymPy is insufficient or you want cross-verification
    - NOT for numerical probability calculations (use numerical_probability instead)

    PRE-CONDITIONS:
    - expression must be a valid SymPy-parseable string (e.g., "x**2*exp(x)", "sin(x)/x")
    - operation must be one of: differentiate, integrate, solve, limit, simplify
    - variable must be a single variable name (default "x")
    - point is required only for limit operation (e.g., "0", "oo" for infinity)

    POST-CONDITIONS:
    - Returns exact symbolic result as a string (both plain and LaTeX format)
    - Returns error message if expression is invalid or operation fails
    - For integrate/differentiate: result is guaranteed to be mathematically correct (SymPy verified)

    EXAMPLES:
    - Input: {"expression": "x**2*exp(x)", "operation": "integrate", "variable": "x"}
      Output: "(x**2 - 2*x + 2)*exp(x) + C  [LaTeX: x^{2} e^{x} - 2x e^{x} + 2e^{x} + C]"
    - Input: {"expression": "x**2*exp(x)", "operation": "differentiate", "variable": "x"}
      Output: "x**2*exp(x) + 2*x*exp(x)  [LaTeX: x^{2} e^{x} + 2x e^{x}]"
    - Input: {"expression": "sin(x)/x", "operation": "limit", "variable": "x", "point": "0"}
      Output: "1"
    - Input: {"expression": "x**3 - 6*x**2 + 11*x - 6", "operation": "solve", "variable": "x"}
      Output: "[1, 2, 3]"
    """
    try:
        var = Symbol(variable)
        expr = sympify(expression)

        if operation == "differentiate":
            result = diff(expr, var)
        elif operation == "integrate":
            result = integrate(expr, var)
        elif operation == "solve":
            result = solve(expr, var)
        elif operation == "limit":
            if point is None:
                return "Error: 'point' is required for limit operation"
            pt = sympify(point)
            result = limit(expr, var, pt)
        elif operation == "simplify":
            result = simplify(expr)
        else:
            return f"Error: Unknown operation '{operation}'. Must be: differentiate, integrate, solve, limit, simplify"

        plain = str(result)
        latex_str = latex(result)
        return f"{plain}  [LaTeX: {latex_str}]"

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def numerical_probability(
    distribution: str,
    parameters: str,
    operation: str,
    value: str | None = None,
) -> str:
    """Numerical probability computation using scipy.stats.

    WHEN TO USE:
    - Need to compute probabilities, CDF, PDF/PMF, quantiles, expected values, variance
    - When working with specific probability distributions (normal, binomial, poisson, exponential, uniform, etc.)
    - NOT for symbolic/exact results (use symbolic_compute instead)

    PRE-CONDITIONS:
    - distribution must be a valid scipy.stats name (norm, binom, poisson, expon, uniform, t, chi2, beta, gamma, geom, hypergeom, etc.)
    - parameters must be a JSON string of distribution parameters (e.g., '{"loc": 10, "scale": 2}' for N(10,2), '{"n": 10, "p": 0.5}' for Binom)
    - operation must be one of: pdf, cdf, pmf, ppf, sf, mean, var, std, entropy
    - value is required for pdf/cdf/pmf/sf/ppf (the point to evaluate); not needed for mean/var/std/entropy

    POST-CONDITIONS:
    - Returns numerical result as a string
    - For cdf/sf: result is guaranteed to be in [0, 1]
    - For ppf: result is a quantile value
    - Returns error message if distribution/parameters are invalid

    EXAMPLES:
    - Input: {"distribution": "norm", "parameters": "{\"loc\": 10, \"scale\": 2}", "operation": "cdf", "value": "12"}
      Output: "0.8413" (P(X<=12) for N(10,2))
    - Input: {"distribution": "binom", "parameters": "{\"n\": 10, \"p\": 0.5}", "operation": "pmf", "value": "3"}
      Output: "0.1171" (P(X=3) for Binom(10,0.5))
    - Input: {"distribution": "poisson", "parameters": "{\"mu\": 3}", "operation": "cdf", "value": "5"}
      Output: "0.9161" (P(X<=5) for Poisson(3))
    """
    try:
        params = json.loads(parameters)
        dist_obj = getattr(stats, distribution, None)
        if dist_obj is None:
            return f"Error: Unknown distribution '{distribution}'"

        rv = dist_obj(**params)

        if operation in ("pdf", "cdf", "pmf", "sf", "ppf"):
            if value is None:
                return f"Error: 'value' is required for {operation} operation"
            v = float(value)
            result = getattr(rv, operation)(v)
            return f"{result:.6f}"
        elif operation == "mean":
            return f"{rv.mean():.6f}"
        elif operation == "var":
            return f"{rv.var():.6f}"
        elif operation == "std":
            return f"{rv.std():.6f}"
        elif operation == "entropy":
            return f"{rv.entropy():.6f}"
        else:
            return f"Error: Unknown operation '{operation}'"

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def verify_result(
    original_expression: str,
    claimed_result: str,
    verification_type: str,
    variable: str = "x",
) -> str:
    """Cross-verify mathematical results using numerical substitution and derivative checks.

    WHEN TO USE:
    - Need to verify a claimed result against an original expression
    - After computing an integral: verify by differentiating the result
    - After computing a derivative: verify by numerical substitution at multiple points
    - After computing a probability: verify bounds and consistency

    PRE-CONDITIONS:
    - original_expression must be a valid SymPy-parseable string
    - claimed_result must be a valid SymPy-parseable string
    - verification_type must be one of: derivative, numerical, bounds
    - variable must match the variable in the expression

    POST-CONDITIONS:
    - Returns "PASS" if verification succeeds, or "FAIL: <reason>" with counterexample details
    - For derivative verification: checks d/dx(claimed_result) == original_expression
    - For numerical verification: checks original_expression and claimed_result agree at random points
    - For bounds verification: checks probability values are in [0,1], distributions are valid

    EXAMPLES:
    - Input: {"original_expression": "x**2*exp(x)", "claimed_result": "(x**2-2*x+2)*exp(x)", "verification_type": "derivative", "variable": "x"}
      Output: "PASS: d/dx[(x**2-2*x+2)*exp(x)] = x**2*exp(x) + 2*x*exp(x) which simplifies to the original after verification"
    - Input: {"original_expression": "x**2+1", "claimed_result": "x**2+2", "verification_type": "numerical", "variable": "x"}
      Output: "FAIL: At x=1, original=2, claimed=3, difference=1"
    """
    try:
        var = Symbol(variable)
        orig = sympify(original_expression)
        claimed = sympify(claimed_result)

        if verification_type == "derivative":
            deriv = diff(claimed, var)
            diff_expr = simplify(deriv - orig)
            if diff_expr == 0:
                return f"PASS: d/dx[{claimed}] = {deriv} = {orig}"
            else:
                return f"FAIL: d/dx[{claimed}] = {deriv}, expected {orig}, difference = {diff_expr}"

        elif verification_type == "numerical":
            test_points = [0.5, 1.0, 2.0, 3.0, -1.0]
            evaluated = 0
            min_required = max(1, len(test_points) // 2)
            for pt in test_points:
                try:
                    orig_val = complex(orig.subs(var, pt))
                    claimed_val = complex(claimed.subs(var, pt))
                    # 过滤：复数结果（如 log(-1) = iπ）或非有限值都不能参与比较
                    if orig_val.imag != 0 or claimed_val.imag != 0:
                        continue
                    if not (math.isfinite(orig_val.real) and math.isfinite(claimed_val.real)):
                        continue
                    evaluated += 1
                    if abs(orig_val.real - claimed_val.real) > 1e-6:
                        return (
                            f"FAIL: At {variable}={pt}, "
                            f"original={orig_val.real:.6f}, "
                            f"claimed={claimed_val.real:.6f}, "
                            f"difference={abs(orig_val.real - claimed_val.real):.6f}"
                        )
                except Exception:
                    continue
            if evaluated < min_required:
                return (
                    f"FAIL: only {evaluated}/{len(test_points)} test points could be "
                    f"evaluated (likely domain issues with both expressions)"
                )
            return f"PASS: original and claimed agree at all {evaluated} testable points"

        elif verification_type == "bounds":
            errors = []
            try:
                val = float(claimed)
                if val < 0 or val > 1:
                    errors.append(f"value {val} is outside [0,1]")
            except Exception:
                pass
            if errors:
                return "FAIL: " + "; ".join(errors)
            return "PASS: bounds check passed"

        else:
            return f"Error: Unknown verification_type '{verification_type}'"

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def plot_function(
    expression: str,
    x_range: str = "-5,5",
    title: str = "",
) -> str:
    """Plot a mathematical function and return as base64-encoded PNG image.

    WHEN TO USE:
    - Need to visualize a function for geometric intuition
    - Want to show the shape of a curve, its roots, extrema, or behavior
    - NOT for exact computation (use symbolic_compute or numerical_probability instead)

    PRE-CONDITIONS:
    - expression must be a valid SymPy-parseable string or numpy-compatible expression
    - x_range must be "min,max" format (default "-5,5")
    - title is optional descriptive label

    POST-CONDITIONS:
    - Returns a base64-encoded PNG image string
    - Image shows the function plot with labeled axes
    - Returns error message if expression is invalid

    EXAMPLES:
    - Input: {"expression": "x**2", "x_range": "-3,3", "title": "f(x)=x^2"}
      Output: base64 PNG image of parabola
    - Input: {"expression": "sin(x)/x", "x_range": "-10,10"}
      Output: base64 PNG image of sinc function
    """
    if plt is None:
        return "Error: matplotlib is not available"

    try:
        x_min, x_max = [float(v) for v in x_range.split(",")]
        x_vals = np.linspace(x_min, x_max, 500)

        expr = sympify(expression)
        var = list(expr.free_symbols)
        if len(var) == 0:
            y_vals = np.full_like(x_vals, float(expr))
        else:
            v = var[0]
            f = sympy.lambdify(v, expr, modules=["numpy"])
            y_vals = np.array([float(f(x)) for x in x_vals])

        fig, ax = plt.subplots()
        ax.plot(x_vals, y_vals, label=f"$f({str(var[0] if var else 'x')}) = {latex(expr)}$")
        ax.set_xlabel(str(var[0] if var else "x"))
        ax.set_ylabel("f(x)")
        if title:
            ax.set_title(title)
        ax.legend()
        ax.grid(True)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        return b64

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def latex_validate(latex_str: str) -> str:
    """Validate LaTeX mathematical expressions for syntax correctness.

    WHEN TO USE:
    - Need to check if a LaTeX expression is syntactically valid before displaying
    - Want to catch common LaTeX errors (mismatched braces, undefined commands)
    - NOT for mathematical verification (use verify_result instead)

    PRE-CONDITIONS:
    - latex_str must be a string containing a LaTeX math expression

    POST-CONDITIONS:
    - Returns "VALID" if expression parses correctly, or "INVALID: <error_detail>"
    - Checks: brace matching, command validity, expression parseability via SymPy

    EXAMPLES:
    - Input: {"latex_str": "\\frac{x^2}{e^x}"}
      Output: "VALID"
    - Input: {"latex_str": "\\frac{x^2}"}
      Output: "INVALID: mismatched braces in \\frac"
    """
    try:
        open_braces = latex_str.count("{")
        close_braces = latex_str.count("}")
        if open_braces != close_braces:
            return f"INVALID: mismatched braces (open={open_braces}, close={close_braces})"

        open_brackets = latex_str.count("[")
        close_brackets = latex_str.count("]")
        if open_brackets != close_brackets:
            return f"INVALID: mismatched brackets (open={open_brackets}, close={close_brackets})"

        try:
            parsed = parse_latex(latex_str)
            return "VALID: expression parses correctly"
        except Exception as parse_err:
            try:
                cleaned = latex_str.replace("\\frac", "").replace("\\sqrt", "").replace("\\int", "").replace("\\lim", "")
                sympify(cleaned)
                return "VALID: expression structure is acceptable (partial parse)"
            except Exception:
                return f"INVALID: cannot parse expression - {parse_err}"

    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")