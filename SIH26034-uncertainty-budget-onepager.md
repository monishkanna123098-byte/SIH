# The Uncertainty Budget — One Page

**What U is.** Every measured height carries an expanded uncertainty, U, at a
95%-confidence coverage factor of k=2. A verdict is never "the number is above
the line" — it's COMPLIANT only if the number *minus* U still clears the
line, DEFICIENT only if the number *plus* U still falls short, and honestly
**indeterminate** if U is wide enough that the line falls inside the band.
Current reference value: **U(k=2) = 0.16634 mm at a 1 mm character height**,
version 7.9.

**Three of eight terms scale with height; five don't.** A term like ink-edge
ambiguity is a fixed distance in the image plane — a half-pixel is a
half-pixel whether the character is 1mm or 6mm tall. But scale calibration,
lens distortion, and fiducial localisation are *fractional* errors — a
0.1%-of-height error is ten times bigger at 10mm than at 1mm. Since v7.3, the
budget scales those three correctly, so **U rises with the requirement**:
0.16634mm at 1mm, 0.18486mm at 2mm, 0.28578mm at 6mm. U is always evaluated
at max(measured height, threshold) — never the smaller of the two — so a
package measuring below its requirement can't get a narrower, more confident
band than one measuring above it.

**The eight terms, plainly:**

| Term | mm (at 1mm ref) | Kind | Status |
|---|---|---|---|
| Ink-spread / cap ambiguity | 0.080 | systematic | modelled — the dominant term |
| Repeatability (pose) | 0.030 | random | modelled — placeholder pending re-seating trials |
| Scale calibration | 0.010 | random, scales with height | modelled — placeholder pending stage micrometer |
| Lens distortion (field position) | 0.010 | systematic, scales with height | modelled |
| Convention-bias residual | 0.005 | systematic | modelled |
| Defocus / PSF asymmetry | 0.005 | systematic | modelled |
| Edge localisation | 0.010 | random | modelled |
| Fiducial localisation | 0.0005 | random, scales with height | modelled |

**All eight are still *modelled*, not *measured*.** That's not a weakness to
hide — it's the honest state, and it's why every printed U carries a
"2 d.p." caveat instead of pretending to a precision the budget hasn't
earned. The plan for Sep 10 converts the first one: a stage-micrometer
session at field centre and all four corners gives `check_field_uniformity`
a real spread to close `lens_distortion_field_position`, and a two-point
scale session gives `ScaleReference.type_a_sd_mm()` a measured repeatability
that can replace (not add to) the modelled scale-calibration term — read that
function's own docstring caveat before doing the substitution; it only
applies if the v7 term is pure repeatability, not standing in for pitch or
printer error too.

**Say this, don't hide it:** "Every number here is an engineering estimate
until the stage-micrometer run. That's not a gap in the argument — refusing
to call an estimate a measurement *is* the argument."
