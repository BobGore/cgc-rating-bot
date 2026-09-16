"""Online rating -> USCF-equivalent, using the ChessGoals July 2026 fits.

Every mapping pivots on Chess.com blitz: the site fits one cubic per target
rating pool, all with blitz as the input variable. A non-blitz rating is
therefore inverted back to blitz first, then pushed through the USCF cubic.

The fits are only valid for blitz 500-3000. Outside that the cubics diverge
(the old bot extrapolated and turned a lichess classical 1165 into a 225),
so anything out of range raises rather than returning a number.
"""

# Which ChessGoals fit COEFFS below was taken from. Shown to users via
# !helpratingbot - update this alongside COEFFS whenever the fits are
# refitted, so the displayed version never drifts from what's actually
# being used.
FIT_VERSION = "July 2026"

# a*x^3 + b*x^2 + c*x + d, where x is Chess.com blitz.
COEFFS = {
    "cc_bullet": (-5.43772231680863e-8, 0.000344377955797529, 0.326912399827871, 305.293854154169),
    "cc_rapid": (-2.22197749041556e-8, -0.0000180165271960034, 0.948661848727365, 347.999323268142),
    "li_blitz": (5.61723492431518e-9, -0.0000283814790928676, 0.700598508687725, 746.710939059583),
    "li_bullet": (-1.97493776947396e-8, 0.000156223417417083, 0.429101409179833, 808.276998829128),
    "li_rapid": (8.83842486450288e-9, -0.00010206500694963, 0.792911754318979, 917.749690646877),
    "li_classical": (-3.57441631149992e-8, 0.000170045372917626, 0.173020865120641, 1380.86562310617),
    "uscf": (3.80677508646207e-8, -0.000210281923145702, 0.970069956373032, 487.494871995394),
}

BLITZ_MIN = 500
BLITZ_MAX = 3000

# Published tables round to the nearest 5; allow that much slack at the edges.
EDGE_TOLERANCE = 5


class OutOfRange(ValueError):
    """Rating falls outside the range the ChessGoals fits cover."""


def _poly(x, coeffs):
    a, b, c, d = coeffs
    return a * x**3 + b * x**2 + c * x + d


def _to_blitz(rating, source):
    """Invert a source cubic back to its Chess.com blitz equivalent.

    Every cubic in COEFFS is strictly increasing across 500-3000 (verified
    against the published tables), so bisection is exact. The FIDE cubic is
    NOT monotonic below blitz 1047 and is deliberately absent for that reason.
    """
    if source == "cc_blitz":
        if not BLITZ_MIN <= rating <= BLITZ_MAX:
            raise OutOfRange(f"blitz {rating} is outside {BLITZ_MIN}-{BLITZ_MAX}")
        return float(rating)

    coeffs = COEFFS[source]
    floor, ceiling = _poly(BLITZ_MIN, coeffs), _poly(BLITZ_MAX, coeffs)
    # The published tables round to the nearest 5, so a rating taken straight
    # from them can sit a whisker outside the unrounded domain (lichess
    # classical 1505 vs a true floor of 1505.3). Snap those to the boundary.
    if floor - EDGE_TOLERANCE <= rating < floor:
        return float(BLITZ_MIN)
    if ceiling < rating <= ceiling + EDGE_TOLERANCE:
        return float(BLITZ_MAX)
    if not floor <= rating <= ceiling:
        raise OutOfRange(f"{source} {rating} is outside {floor:.0f}-{ceiling:.0f}")

    low, high = float(BLITZ_MIN), float(BLITZ_MAX)
    for _ in range(40):
        mid = (low + high) / 2
        if _poly(mid, coeffs) < rating:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def to_uscf(rating, source):
    """Convert an online rating to a USCF-equivalent, rounded to the nearest 5.

    Raises OutOfRange if the rating falls outside the fitted domain.
    """
    blitz = _to_blitz(rating, source)
    return round(_poly(blitz, COEFFS["uscf"]) / 5) * 5
