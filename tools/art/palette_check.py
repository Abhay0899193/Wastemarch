#!/usr/bin/env python3
"""Numeric safety check for the Wastemarch colour palette.

    python3 tools/art/palette_check.py

`docs/ART_BIBLE.md` says the palette may not be locked without a colourblind
check and a look at how the colours separate at phone size. This is that check,
as arithmetic rather than opinion, so it can be re-run whenever a value moves.

What it reports, per pair of colours:

  dL   difference in perceived lightness (CIE L*, 0..100). This is the number
       that matters most. A phone at half brightness in daylight destroys
       subtle hue differences long before it destroys lightness differences.
  dE   CIE76 colour difference in Lab space. Roughly: below 10 the two are
       easy to confuse at a glance, below 5 they are nearly the same colour.
  dH   hue angle difference in degrees.

and then repeats dE under simulated deuteranopia, protanopia and tritanopia
(the three common forms of colour blindness), using the Viénot-Brettel-Mollon
1999 method.

The pass/fail rules encode the Art Bible's own priorities:

  * Colours with DIFFERENT JOBS must stay apart. Two colours that mean
    different things to the player and collapse under a colourblind
    simulation are a real defect.
  * Colours with the SAME JOB are allowed to be close. Dead soil and bone grey
    are both "the drab environment"; confusing them costs nothing.

Stdlib only, on purpose — this must run on any machine with no setup.
"""

import math

# ---------------------------------------------------------------------------
# The palette under test. Roles come from docs/ART_BIBLE.md.
#
# `job` groups colours that carry the SAME meaning to the player. Pairs inside
# a group are exempt from the separation rules; pairs across groups are not.
#
# The job "LIGHT-NOT-SURFACE" is exempt from every comparison. That colour is
# never painted on anything — it is the tint of a light source and the glow it
# throws. It is always seen next to its own bright core and against whatever it
# is illuminating, never as a flat fill beside another palette colour, so
# comparing it to an albedo colour answers a question nobody asks.
# ---------------------------------------------------------------------------

PALETTE = [
    # name,             hex,        job
    ("Dead soil",       "#8B8071",  "environment"),
    ("Bone grey",       "#C4BCAE",  "environment"),
    ("Dry ochre",       "#9B8459",  "environment"),
    ("Duskwood near",   "#1C2E2C",  "environment-dark"),
    ("Duskwood deep",   "#0A1412",  "environment-dark"),
    ("Ostmere crimson", "#8C2323",  "faction"),
    ("Ostmere gold",    "#C4942F",  "wealth"),
    ("Firelight core",  "#F7CE7C",  "life"),
    ("Firelight glow",  "#E8A54B",  "LIGHT-NOT-SURFACE"),
    ("Duskglass",       "#3E7C8C",  "rare-resource"),
]

# A pair of colours with different jobs must clear these, or a player cannot
# reliably tell them apart on a phone.
MIN_DE_NORMAL = 20.0      # CIE76 in normal vision
MIN_DE_CVD = 12.0         # ...and under each colourblind simulation
MIN_DL_SAME_HUE = 8.0     # lightness separation when hues are within 20 degrees


# ---------------------------------------------------------------------------
# Colour space conversions. sRGB -> linear -> XYZ -> Lab.
# ---------------------------------------------------------------------------

def hex_to_srgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_linear(c):
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def linear_to_srgb(c):
    out = []
    for v in c:
        v = max(0.0, min(1.0, v))
        out.append(v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)
    return tuple(out)


def linear_to_xyz(c):
    r, g, b = c
    return (
        0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
        0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
        0.0193339 * r + 0.1191920 * g + 0.9503041 * b,
    )


def xyz_to_lab(xyz):
    # D65 white point.
    xn, yn, zn = 0.95047, 1.00000, 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(xyz[0] / xn), f(xyz[1] / yn), f(xyz[2] / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def hex_to_lab(h):
    return xyz_to_lab(linear_to_xyz(srgb_to_linear(hex_to_srgb(h))))


def relative_luminance(h):
    """WCAG relative luminance, for the plain light/dark question."""
    return linear_to_xyz(srgb_to_linear(hex_to_srgb(h)))[1]


def contrast_ratio(h1, h2):
    a, b = relative_luminance(h1), relative_luminance(h2)
    lo, hi = min(a, b), max(a, b)
    return (hi + 0.05) / (lo + 0.05)


def lab_hue(lab):
    return math.degrees(math.atan2(lab[2], lab[1])) % 360


def lab_chroma(lab):
    return math.hypot(lab[1], lab[2])


def delta_e76(l1, l2):
    return math.dist(l1, l2)


def hue_gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ---------------------------------------------------------------------------
# Colour blindness simulation — Viénot, Brettel & Mollon 1999.
#
# Each matrix projects linear RGB onto the plane of colours that form of colour
# blindness can actually distinguish. Two colours whose simulations land in the
# same place are indistinguishable to that viewer.
# ---------------------------------------------------------------------------

CVD_MATRICES = {
    "deuteranopia": (  # no green cone. The most common form, ~6% of men.
        (0.625, 0.375, 0.0),
        (0.700, 0.300, 0.0),
        (0.0, 0.300, 0.700),
    ),
    "protanopia": (  # no red cone, ~2% of men.
        (0.1115, 0.8885, 0.0),
        (0.1115, 0.8885, 0.0),
        (0.0040, -0.0040, 1.0),
    ),
    "tritanopia": (  # no blue cone. Rare, but it is what hits teal.
        (0.9500, 0.0500, 0.0),
        (0.0, 0.4333, 0.5667),
        (0.0, 0.4750, 0.5250),
    ),
}


def simulate_cvd(h, kind):
    lin = srgb_to_linear(hex_to_srgb(h))
    m = CVD_MATRICES[kind]
    out = tuple(sum(m[r][c] * lin[c] for c in range(3)) for r in range(3))
    return linear_to_srgb(out)


def cvd_lab(h, kind):
    return xyz_to_lab(linear_to_xyz(srgb_to_linear(simulate_cvd(h, kind))))


def to_hex(srgb):
    return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02X}" for v in srgb)


# ---------------------------------------------------------------------------

def main():
    labs = {n: hex_to_lab(h) for n, h, _ in PALETTE}
    jobs = {n: j for n, _, j in PALETTE}
    hexes = {n: h for n, h, _ in PALETTE}

    print("=" * 78)
    print("PER COLOUR")
    print("=" * 78)
    print(f"{'name':<17}{'hex':<9}{'L*':>6}{'chroma':>8}{'hue':>7}   grey")
    for name, h, _ in PALETTE:
        lab = labs[name]
        grey = round(relative_luminance(h) ** (1 / 2.2) * 255)
        print(f"{name:<17}{h:<9}{lab[0]:>6.1f}{lab_chroma(lab):>8.1f}"
              f"{lab_hue(lab):>7.0f}   #{grey:02X}{grey:02X}{grey:02X}")

    print()
    print("=" * 78)
    print("PAIRS THAT MUST STAY APART  (different jobs)")
    print("=" * 78)

    failures = []
    warnings = []
    names = [n for n, _, _ in PALETTE]

    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if jobs[a] == jobs[b] or "LIGHT-NOT-SURFACE" in (jobs[a], jobs[b]):
                continue
            la, lb = labs[a], labs[b]
            de = delta_e76(la, lb)
            dl = abs(la[0] - lb[0])
            dh = hue_gap(lab_hue(la), lab_hue(lb))
            cvd = {k: delta_e76(cvd_lab(hexes[a], k), cvd_lab(hexes[b], k))
                   for k in CVD_MATRICES}
            worst_kind = min(cvd, key=cvd.get)
            rows.append((min(de, min(cvd.values())), a, b, de, dl, dh, cvd, worst_kind))

            if de < MIN_DE_NORMAL:
                failures.append(f"{a} vs {b}: dE {de:.1f} in NORMAL vision "
                                f"(want >= {MIN_DE_NORMAL})")
            if min(cvd.values()) < MIN_DE_CVD:
                failures.append(f"{a} vs {b}: dE {cvd[worst_kind]:.1f} under "
                                f"{worst_kind} (want >= {MIN_DE_CVD})")
            elif dh < 20 and dl < MIN_DL_SAME_HUE:
                warnings.append(f"{a} vs {b}: only {dh:.0f} deg apart in hue and "
                                f"{dl:.1f} in lightness — will merge at phone size")

    rows.sort()
    print(f"{'pair':<38}{'dE':>6}{'dL*':>7}{'dHue':>6}"
          f"{'deut':>7}{'prot':>7}{'trit':>7}")
    for _, a, b, de, dl, dh, cvd, _ in rows:
        pair = f"{a} / {b}"
        flag = "  <-- " if min(de, min(cvd.values())) < MIN_DE_CVD else ""
        print(f"{pair:<38}{de:>6.1f}{dl:>7.1f}{dh:>6.0f}"
              f"{cvd['deuteranopia']:>7.1f}{cvd['protanopia']:>7.1f}"
              f"{cvd['tritanopia']:>7.1f}{flag}")

    print()
    print("=" * 78)
    print("WHAT A COLOURBLIND PLAYER SEES")
    print("=" * 78)
    print(f"{'name':<17}{'normal':<10}{'deuter.':<10}{'protan.':<10}{'tritan.':<10}")
    for name, h, _ in PALETTE:
        sims = [to_hex(simulate_cvd(h, k)) for k in
                ("deuteranopia", "protanopia", "tritanopia")]
        print(f"{name:<17}{h:<10}" + "".join(f"{s:<10}" for s in sims))

    # The palette lives in two places: here, where it is checked, and in the Art
    # Bible, where it is read by a human and by every image-generation prompt.
    # Duplication is unavoidable — a prompt cannot import Python — so it is
    # pinned instead. Editing one and not the other is the realistic mistake.
    bible_note = None
    try:
        with open("docs/ART_BIBLE.md") as fh:
            bible = fh.read().upper()
    except OSError:
        bible_note = ("warn", "could not read docs/ART_BIBLE.md — sync check skipped")
    else:
        missing = [f"{n} {h}" for n, h, _ in PALETTE if h.upper() not in bible]
        if missing:
            failures.append("docs/ART_BIBLE.md does not list: " + ", ".join(missing))
        else:
            bible_note = ("ok", "docs/ART_BIBLE.md lists every value checked here")

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  FAIL  {f}")
    else:
        print("  ok    every pair with a different job stays distinguishable,")
        print("        including under all three colourblind simulations")
    if bible_note:
        print(f"  {bible_note[0]:<5} {bible_note[1]}")
    for w in warnings:
        print(f"  warn  {w}")

    print()
    print("Contrast of firelight against the two darks it has to read on top of:")
    for dark in ("Duskwood near", "Duskwood deep"):
        r = contrast_ratio(hexes["Firelight core"], hexes[dark])
        print(f"  Firelight core on {dark:<15} {r:>5.1f}:1")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
