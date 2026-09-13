"""Sanity-check the conversion coefficients after an annual update.

_to_blitz uses bisection, which is only correct if each source cubic rises
monotonically across the fitted domain. That holds for the current fits but
is a property of the data, not something the code enforces — a non-monotonic
cubic makes bisection return a plausible but wrong answer instead of failing.
The FIDE cubic is non-monotonic below blitz 1047, which is why it is excluded.

Run this before trusting new coefficients:  python3 check_coeffs.py
"""

from conversion import BLITZ_MAX, BLITZ_MIN, COEFFS, _poly

if __name__ == "__main__":
    failed = False
    for name, coeffs in COEFFS.items():
        values = [_poly(x, coeffs) for x in range(BLITZ_MIN, BLITZ_MAX + 1)]
        monotonic = all(b >= a for a, b in zip(values, values[1:]))
        failed |= not monotonic
        print(
            f"{name:14s} {'ok  ' if monotonic else 'FAIL'} "
            f"{values[0]:7.0f} -> {values[-1]:7.0f}"
        )
    raise SystemExit(1 if failed else 0)
