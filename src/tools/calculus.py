CALCULUS_REFERENCE = """\
# SymPy Calculus Toolkit Reference

## Symbol Setup
from sympy import Symbol, symbols, var
x = Symbol('x')
y = Symbol('y')
x, y, z = symbols('x y z')

## Derivatives
from sympy import diff, Derivative
diff(x**3 + 2*x, x)              # ordinary derivative
diff(x**3 + 2*x, x, 2)           # second derivative
diff(x*y**2 + y*x**3, x, y)      # partial derivatives

## Integrals
from sympy import integrate, Integral
integrate(x**2, x)                # indefinite integral
integrate(x**2, (x, 0, 1))       # definite integral from 0 to 1
integrate(sin(x), (x, 0, pi))    # definite integral with symbolic bounds

## Limits
from sympy import limit, Limit, oo
limit(sin(x)/x, x, 0)            # limit as x->0
limit(1/x, x, oo)                # limit as x->infinity
limit(x**2, x, 0, '+')           # one-sided limit (right)
limit(x**2, x, 0, '-')           # one-sided limit (left)

## Series / Taylor Expansion
from sympy import series
series(sin(x), x, 0, 6)          # Taylor series around 0, up to x^5

## Equation Solving
from sympy import solve, Eq
solve(x**2 - 4, x)               # solve polynomial
solve(Eq(x**2 + y, y**2), x)     # solve for x in terms of y

## Simplification & Display
from sympy import simplify, expand, factor, latex, pprint
simplify((x**2 - 4)/(x - 2))     # simplify expression
expand((x+1)**3)                  # expand
factor(x**2 - 4)                  # factor
latex(result)                     # LaTeX output

## Common Functions
from sympy import sin, cos, tan, exp, log, sqrt, pi, E, oo, factorial
"""

PROBABILITY_REFERENCE = """\
# Probability Theory Toolkit Reference (scipy + SymPy + math)

## Discrete Probability
from math import factorial, comb
from itertools import combinations, product
comb(n, k)                        # binomial coefficient C(n,k)

## SymPy for symbolic probability
from sympy import Symbol, Rational, factorial as sfact
p = Symbol('p', positive=True)
# Bayes theorem: P(A|B) = P(B|A)*P(A) / P(B)

## scipy.stats for numerical distributions
from scipy.stats import norm, binom, poisson, expon, uniform, chi2, t

### Normal Distribution
norm.pdf(x, mu, sigma)            # PDF at x
norm.cdf(x, mu, sigma)            # CDF at x (P(X<=x))
norm.ppf(q, mu, sigma)            # quantile (inverse CDF)
norm.mean(mu, sigma)              # mean
norm.var(mu, sigma)               # variance
norm.std(mu, sigma)               # std deviation

### Binomial Distribution
binom.pmf(k, n, p)                # P(X=k) for Bin(n,p)
binom.cdf(k, n, p)                # P(X<=k)
binom.mean(n, p)                  # expected value = n*p
binom.var(n, p)                   # variance = n*p*(1-p)

### Poisson Distribution
poisson.pmf(k, mu)                # P(X=k) for Pois(mu)
poisson.cdf(k, mu)                # P(X<=k)
poisson.mean(mu)                  # expected value = mu

### Uniform Distribution
uniform.pdf(x, loc, scale)        # PDF on [loc, loc+scale]
uniform.cdf(x, loc, scale)        # CDF
uniform.mean(loc, scale)          # mean = loc + scale/2

### Exponential Distribution
expon.pdf(x, scale=1/lambda_)     # PDF
expon.cdf(x, scale=1/lambda_)     # CDF
expon.mean(scale=1/lambda_)       # mean = 1/lambda_

## Combinatorics
from math import factorial, comb, perm
from itertools import combinations, permutations
factorial(n)                      # n!
comb(n, k)                        # C(n,k)
perm(n, k)                        # P(n,k)
"""