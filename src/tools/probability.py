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