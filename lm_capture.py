"""
lm_capture.py — the fixed-rig capture path for SIH26034.

WHAT THIS IS FOR
----------------
Every other team at the internal round will demo a screen. The one thing this
project has that cannot be faked in three minutes is an instrument on a table,
and until now there was no code between the camera and the measurement engine —
the pipeline ate stills that came from somewhere unrecorded. "Somewhere
unrecorded" is not an evidence chain.

THE ONE RULE THIS MODULE EXISTS TO ENFORCE
------------------------------------------
No scale reference in frame, no millimetres. Not a warning, not a default, not a
remembered value from last time: a refusal. This is the project's whole thesis
placed at the earliest point where it can be violated, because every downstream
number inherits mm-per-pixel and a wrong scale is invisible in the output — the
edges are still crisp, the verdict still prints, the uncertainty budget still
looks respectable, and everything is wrong by a factor nobody can see.

That also makes it the best twenty seconds of the demo. Point the camera at a
packet with nothing of known size in frame: it refuses. Slide the calibration
artifact into frame: it measures. A heuristic font checker cannot do the first
half.

STANDARD VERSUS SPECIMEN, ENFORCED IN CODE
------------------------------------------
A printed calibration target is a SPECIMEN: paper whose true pitch is whatever
the printer did. A graduated glass artifact is a STANDARD: a nominal value someone
else certified, or at least stated. Both recover a px/mm. They do not carry the
same authority, and a specimen quietly acquiring a standard's authority is the
same failure the legal layer's source tiers exist to prevent. So scale carries a
tier, exactly like `Provenance` does in lm_legal_model.py, and the tier travels
with every measurement made under it.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
  * No measuring. It hands off a frame plus a `ScaleReference`; heights are
    lm_metrology_v7.py's job. The handoff is one object, `SpecimenCapture`, and
    the INTEGRATION block at the foot of the file is the wiring instruction.
  * No lens undistortion. There is no lens model anywhere in this project and
    inventing one here would be an unmeasured correction, which is worse than a
    disclosed uncalibrated lens. The field-position check on the rig is what
    turns that into a number.
  * No panel segmentation, no OCR, no legal lookup.

STATUS: NOTHING IN THIS FILE HAS BEEN EXECUTED BY ITS AUTHOR.
No Python environment was available (VM_DISK_SPACE_INSUFFICIENT for nine
consecutive sessions) and no camera was attached to anything. `self_test()` is
camera-free by construction and is the first thing to run. Treat the OpenCV calls
as unverified against the installed version — they are the most likely thing in
here to be wrong, and they are isolated in `_backend()` for that reason.
"""

from __future__ import annotations

import math
import time
from dataclasses import MISSING, dataclass, field, fields

# --------------------------------------------------------------------------
# Scale tiers. Same two-axis idea as the legal layer: where the scale came from
# and how much it can carry are different questions.
# --------------------------------------------------------------------------
SCALE_FROM_CERTIFIED = "CERTIFIED_STANDARD"    # calibration certificate exists
SCALE_FROM_STANDARD = "UNCERTIFIED_STANDARD"   # glass graticule, stated pitch
SCALE_FROM_SPECIMEN = "PRINTED_SPECIMEN"       # printed target, printer accuracy
SCALE_FROM_DECLARED = "OPERATOR_DECLARED"      # "that gap is 20 mm, trust me"

# Ordered worst to best. Used to detect a CHANGE in authority mid-session, in
# either direction — not to refuse an upgrade. The direction is reported because
# it is useful to know; the refusal is about the change going unnoticed.
_TIER_RANK = {
    SCALE_FROM_DECLARED: 0,
    SCALE_FROM_SPECIMEN: 1,
    SCALE_FROM_STANDARD: 2,
    SCALE_FROM_CERTIFIED: 3,
}

# The engineering floor from lm_metrology_v7.py. Repeated here as a named
# constant rather than imported, because importing v7 to learn one number would
# couple the capture path to a source whose identifiers are unverified.
MIN_PX_PER_MM = 30.0        # engineering target; NOT a proven minimum

# How many frames a scale session averages, and how tight the spread must be.
# The spread is the useful part: it is the FIRST term in this project's budget
# that can be measured rather than modelled, and it costs five minutes on a
# table. Read the caveat on `ScaleReference.type_a_sd_mm` before quoting it.
SCALE_SESSION_FRAMES = 12
SCALE_SPREAD_REJECT_REL = 0.004     # 0.4% relative sd across frames -> unstable

# Focus gate. Variance-of-Laplacian is scene-dependent, so an absolute threshold
# is meaningless; what is meaningful is a drop against a baseline taken on the
# calibration artifact at best focus, on this rig, in this session.
FOCUS_FLOOR_FRACTION = 0.55


# --------------------------------------------------------------------------
# Refusals. Separate codes, for the same reason the legal layer has ten: an
# operator who is told "capture failed" learns nothing, and a demo that says
# "capture failed" on stage looks like a crash rather than a decision.
# --------------------------------------------------------------------------
CAP_BACKEND_UNAVAILABLE = "CAPTURE_BACKEND_UNAVAILABLE"
CAP_NO_FRAME = "CAPTURE_NO_FRAME"
CAP_NO_SCALE_REFERENCE = "NO_SCALE_REFERENCE"
CAP_SCALE_AMBIGUOUS = "SCALE_REFERENCE_AMBIGUOUS"
CAP_SCALE_BELOW_FLOOR = "SCALE_BELOW_RESOLUTION_FLOOR"
CAP_SCALE_UNSTABLE = "SCALE_UNSTABLE_ACROSS_FRAMES"
CAP_SCALE_STALE = "SCALE_SESSION_STALE"
CAP_FOCUS_INSUFFICIENT = "FOCUS_INSUFFICIENT"
CAP_NO_FOCUS_BASELINE = "FOCUS_BASELINE_NOT_ESTABLISHED"
# Named for what it detects (a change), not for one direction of it. The earlier
# draft of this constant said DOWNGRADE while the code refused an upgrade — the
# same mislabelled-semantics defect this project has logged before, caught in
# review rather than on stage this time.
CAP_TIER_CHANGED = "SCALE_TIER_CHANGED_MID_SESSION"
CAP_FIELD_NONUNIFORM = "FIELD_SCALE_NONUNIFORM"

# The budget allows 0.010 mm on a 1 mm glyph for lens distortion at field
# position, i.e. 1.0% relative. That allowance is the derived limit for the
# measured field spread below — same pattern as v7's gradient_limit_from_budget,
# which derives a capture limit from an induced-error target rather than picking
# a round number and calling it a spec.
LENS_FIELD_TERM_REL = 0.010

# Localisation error on ONE feature, in pixels, propagated to the separation of
# two. 0.2 px each, independent, gives 0.2*sqrt(2) = 0.283 px on the separation.
# The 0.2 px is a detector figure; an operator picking by eye is worse, which is
# why the two-point path takes several picks and lets the spread say so.
_FIDUCIAL_PICK_PX = 0.283
# CORRECTED 2026-09-05. The previous chain ran backwards and the error was in the
# flattering direction, so it is written out in full here.
#
# It said: the budget's fiducial term is 0.0005 mm on a 1 mm glyph, therefore
# hold 0.283/sep <= 0.0005, therefore sep >= 566 px. Both steps are arithmetically
# right and the premise is wrong: THIS RIG CANNOT PRESENT A 566 px BASELINE
# ANYWHERE IN ITS OPERATING RANGE. The shipped artifact's longest span is 10 mm
# and the resolution floor is 30 px/mm, so the longest baseline available is
# 300 px at the floor and 400 px at the planned 40 px/mm. A term derived from a
# 566 px baseline is a term derived from an artifact we do not own.
#
# Two consequences, and the second is why this is a real defect and not a nit.
# The warning below fired on EVERY correct capture, which trains an operator to
# ignore the notes field - and the notes field is where the honest caveats live.
# And the budget term itself was optimistic by 2x, because it was derived from a
# geometry the instrument does not achieve.
#
# So the chain now runs the right way round: artifact span x resolution floor
# gives the achievable baseline, and the term follows from it.
#   10 mm x 30 px/mm = 300 px achievable at the floor
#   0.283 / 300 = 0.000943 mm on a 1 mm glyph, rounded UP to 0.001
#   holding 0.001 needs sep >= 0.283/0.001 = 283 px
# 283 px is 28.3 px/mm on the full 10 mm span, just under MIN_PX_PER_MM, and that
# relationship is the whole point: the two gates are COUPLED, because px/mm on the
# two-point path is separation over DECLARED pitch, so sep = px_per_mm x pitch_mm.
# Any session that survives the resolution floor has sep >= 30 x pitch_mm, which is
# 300 px here and 600 px for the 20 mm target. So on the shipped artifacts this
# warning is STRUCTURALLY SILENT, which is the fixed state of the always-on defect
# and not an accident.
#
# BE HONEST ABOUT WHAT THAT LEAVES. The band 36-283 px opens only when
# 30 x pitch_mm < 283, i.e. an artifact whose declared span is under ~9.4 mm, so
# this is a guard against a future artifact swap: bring a 5 mm graticule, get
# 150 px at the floor, and be told the budgeted term no longer covers the geometry.
# It is NOT a guard against a sub-span read. An earlier draft of this comment
# claimed a 1 mm graduation at 40 px/mm would trip it at 40 px; that read divides
# 40 px by the declared 10 mm and reads as 4 px/mm, so `check_resolution_floor`
# refuses it first and harder. That refusal now names both causes, because 4 px/mm
# does not say whether the camera was too far or the pick was too short.
#
# THE BUDGET CONSEQUENCE, stated so nobody has to rediscover it. The term moves
# 0.0005 -> 0.001 mm, which is a TIGHTENING and therefore cannot be an
# accommodation. Recomputed: random RSS sqrt(0.010^2 + 0.030^2 + 0.010^2 +
# 0.001^2) = sqrt(0.001101) = 0.0331813 against sqrt(0.00110025) = 0.0331700;
# x2 = 0.0663626; + 0.100 systematic = 0.1663626. U(k=2) still quotes as 0.17 mm,
# the band edges still print 0.834 and 1.166, the band is still 33.3% and callable
# shortfall still 16.6%. Only the raw five-decimal figure moves, 0.16634 ->
# 0.16636. Do NOT edit 0.16634 in any document until v7's budget actually carries
# 0.001 and has been re-run: a document that states a number the program does not
# print is the defect this project has logged most often.
MIN_BASELINE_PX = 283.0

# And a hard floor far below that warning level, because the two failures are not
# the same failure. Falling short of the warning level inflates a term that is
# four orders of magnitude below the dominant one, which is a disclosure. A pick of
# a few dozen pixels is not a measurement at all.
#
# Derived, on a stated criterion: a term is negligible while it stays under a
# tenth of the dominant systematic, which is the +/-0.080 mm ink-edge asymmetry.
# 0.283 px / sep_px <= 0.0080 mm on a 1 mm glyph gives sep_px >= 35.4, so 36.
#
# WHAT IT ACTUALLY CATCHES, stated precisely because an earlier draft overstated
# it. This runs inside `scale_from_two_points`, ahead of the resolution floor, so
# it owns the range below 36 px and the floor owns 36 px up to 30 x pitch_mm. It
# was described as catching "one graduation instead of the full span"; that misuse
# lands at 40 px on a 10 mm artifact at 40 px/mm, which is ABOVE this floor and is
# refused by the resolution gate instead. What is left below 36 px is a pick of
# under ~1.2 mm of baseline at the resolution floor - a mis-click, a doubled point,
# a pick on the wrong feature.
#
# Note honestly what the arithmetic shows: the fiducial term is so small that this
# refusal sits at ~1.2 mm of baseline. This gate is not protecting the budget -
# nothing plausible threatens it - it is catching a gross mis-pick. Do not present
# it as a tight tolerance.
ABS_MIN_BASELINE_PX = 36.0
CAP_BASELINE_TOO_SHORT = "SCALE_BASELINE_TOO_SHORT"


# --------------------------------------------------------------------------
# WHICH OF THESE NUMBERS WE CAN DEFEND, RECORDED PER CONSTANT.
#
# Every numeric gate in this file is one of two things, and the difference
# decides what may be done to it when a refusal rate comes back inconvenient:
#
#   DERIVED     - the value follows from a stated allowance, by an argument
#                 written above it. If it fires on ordinary stock the finding
#                 is that our scope is narrower than we claimed. Say so, or fix
#                 the rig that violates the precondition. Do not move the number.
#   PLACEHOLDER - nobody derived it; it was set to something plausible so the
#                 file would run. Setting it deliberately is not tuning, it is
#                 finally doing the work - but the new value needs a physical
#                 argument that would have been just as valid BEFORE the rate
#                 was seen. A limit you would not have chosen before seeing the
#                 outcome is not a limit, it is a fit.
#
# This ledger exists because "measure the refusal rate on real packets" has an
# obvious wrong reading, and Tuesday night is when it gets read that way. The
# deck says out loud that our uncertainty was derived rather than tuned; loosen
# a gate to flatter a demo and that sentence becomes false in the room where we
# say it. self_test() fails if a numeric constant is missing from here, so a gate
# cannot be added without someone deciding which kind it is.
# --------------------------------------------------------------------------
GATE_DERIVED = "DERIVED"
GATE_PLACEHOLDER = "PLACEHOLDER"
# For a numeric constant that decides nothing - a version number, a print width.
# It is NOT a way to retire an inconvenient gate: if a value can cause a refusal
# it is a gate, whatever it is filed as, and filing it here to escape the choice
# between DERIVED and PLACEHOLDER is the laundering this ledger exists to stop.
GATE_NOT_A_GATE = "NOT_A_GATE"

_GATE_PROVENANCE: "dict[str, tuple[str, str]]" = {
    "MIN_PX_PER_MM": (
        GATE_PLACEHOLDER,
        "inherited from v7, whose own comment calls it an engineering target "
        "and not a proven minimum. Deriving it means asking what px/mm the "
        "sub-pixel edge model actually needs, which nobody has done."),
    "SCALE_SESSION_FRAMES": (
        GATE_PLACEHOLDER,
        "12 is a round number, and it is not independent of "
        "SCALE_SPREAD_REJECT_REL - they trade off, and neither was set with "
        "the other in view."),
    "SCALE_SPREAD_REJECT_REL": (
        GATE_PLACEHOLDER,
        "0.4% is chosen, not derived. A check exists - 0.004 across 12 frames "
        "is 0.004/sqrt(12) = 0.115% on the mean, a factor of nine under the "
        "0.010 mm modelled random term - but it assumes the frames are "
        "independent, and consecutive frames of an unmoved target share "
        "whatever bias the detector has. So the check shows the gate is not "
        "dangerous. It does not derive it, and it must not be turned round and "
        "used to shrink the budget term."),
    "FOCUS_FLOOR_FRACTION": (
        GATE_PLACEHOLDER,
        "0.55 of the session baseline. The comment above it concedes that "
        "variance-of-Laplacian is scene-dependent; what it does not say is "
        "that the fraction itself is a guess. Derive it by measuring on this "
        "rig where edge location starts to move."),
    "_SCALE_STALE_SECONDS": (
        GATE_PLACEHOLDER,
        "45 minutes is a round number. It is also the one gate here whose right "
        "value is a procedural question rather than an optical one - how long "
        "does this rig stay put, and does anyone bump the table - so it cannot "
        "be derived from the budget at all. Set it from how the demo is "
        "actually run, and record that reasoning here."),
    "LENS_FIELD_TERM_REL": (
        GATE_DERIVED,
        "the budget's 0.010 mm allowance on a 1 mm glyph, restated as a "
        "relative limit on measured field spread. Note what it is compared "
        "AGAINST: a half-range, i.e. a bound, not a standard deviation. "
        "Gating a bound with an allowance that is a standard uncertainty is "
        "conservative by roughly sqrt(3), and that is deliberate - the glyph "
        "may sit outside the artifact's extent, where the bound is not even "
        "guaranteed to hold."),
    "_FIDUCIAL_PICK_PX": (
        GATE_DERIVED,
        "0.2 px localisation on each of two independent features gives "
        "0.2*sqrt(2) = 0.283 px on their separation. The 0.2 px is a detector "
        "figure; an operator picking by eye is worse, which the two-point "
        "path measures rather than assumes."),
    "MIN_BASELINE_PX": (
        GATE_DERIVED,
        "re-derived 2026-09-05 and the old derivation is worth reading as a "
        "cautionary tale. It ran budget-term -> required baseline and produced "
        "566 px, a baseline the shipped 10 mm artifact cannot present anywhere "
        "in the operating range, so the warning fired on every correct capture "
        "and the term was optimistic by 2x. Now it runs the other way: "
        "10 mm x 30 px/mm = 300 px achievable, term = 0.283/300 = 0.001 mm on "
        "a 1 mm glyph, so hold 0.001 with sep >= 283 px. A tightening of the "
        "budget, not an accommodation. It is now STRUCTURALLY SILENT on both "
        "shipped artifacts, because sep = px_per_mm x declared pitch couples it "
        "to MIN_PX_PER_MM; the band opens only for an artifact under ~9.4 mm of "
        "span, which is the artifact-swap case it guards."),
    "ABS_MIN_BASELINE_PX": (
        GATE_DERIVED,
        "negligible while under a tenth of the 0.080 mm ink-edge asymmetry "
        "gives sep_px >= 35.4, so 36. Derived, and loose on purpose. It owns "
        "the range below 36 px only, because it runs ahead of the resolution "
        "floor which then owns everything up to 30 x declared pitch; so it "
        "catches a gross mis-pick and not, as an earlier note claimed, a "
        "one-graduation read. Do not quote it as a tolerance."),
}


class CaptureRefusal(Exception):
    """Raised instead of returning a frame. Carries a code and a physical cause.

    An exception rather than a return value on purpose: a caller that forgets to
    check a returned refusal gets a frame with no scale and measures it anyway,
    which is precisely the failure this module exists to make impossible.
    """

    def __init__(self, code: str, cause: str) -> None:
        super().__init__("{}: {}".format(code, cause))
        self.code = code
        self.cause = cause


# --------------------------------------------------------------------------
# The artifact the scale is recovered from. `pitch_mm` is DECLARED, always: the
# operator reads it off the graticule or the print job. There is no way to
# discover it from the image, and pretending otherwise is where a fake
# traceability chain would start.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScaleArtifact:
    name: str
    pitch_mm: float                  # separation between the two features used
    tier: str
    certificate_id: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.pitch_mm <= 0.0:
            raise ValueError("pitch_mm must be positive")
        if self.tier not in _TIER_RANK:
            raise ValueError("unknown scale tier {!r}".format(self.tier))
        # A certificate id is what separates CERTIFIED from merely STANDARD. If
        # the id is absent the tier claim is unbacked, and this is the cheapest
        # possible place to catch a team writing CERTIFIED because it reads well.
        if self.tier == SCALE_FROM_CERTIFIED and not self.certificate_id:
            raise ValueError(
                "tier CERTIFIED_STANDARD requires certificate_id; a stated "
                "nominal pitch with no certificate is UNCERTIFIED_STANDARD")


# The two artifacts this project actually has access to, named so the demo does
# not have to construct them from memory at the podium.
GLASS_GRATICULE_1MM = ScaleArtifact(
    name="graduated glass artifact, 10 mm span read end to end",
    pitch_mm=10.0,
    tier=SCALE_FROM_STANDARD,
    note=("Stated nominal span, no calibration certificate. The chain "
          "terminates here: closing it needs a certified artifact or an NABL "
          "comparison. Say that before anyone asks. Use the LONGEST span the "
          "artifact offers, not one division — see MIN_BASELINE_PX."),
)

PRINTED_TARGET_20MM = ScaleArtifact(
    name="printed calibration target, 20 mm fiducial separation",
    pitch_mm=20.0,
    tier=SCALE_FROM_SPECIMEN,
    note=("Paper. Its true separation is whatever the printer did, so this "
          "establishes a scale to printer accuracy and no better. Usable for "
          "exercising the decision bands; NOT usable for validating the scale."),
)

CHESSBOARD_TARGET_5MM = ScaleArtifact(
    name="printed chessboard, 9x6 inner corners, 5 mm squares",
    pitch_mm=5.0,
    tier=SCALE_FROM_SPECIMEN,
    note=("Backup scale artifact for if the glass graticule breaks or goes "
          "missing (execution plan, Sep 8). Paper, same as PRINTED_TARGET_20MM: "
          "printer accuracy, not certified. 5mm squares deliberately, not "
          "smaller -- chessboard_scale()'s own docstring warns that 2mm squares "
          "let cornerSubPix noise alone eat half the field-uniformity "
          "allowance. Pair with run_chessboard_scale_session(session, cap, "
          "CHESSBOARD_TARGET_5MM, inner_cols=9, inner_rows=6, square_mm=5.0)."),
)


# --------------------------------------------------------------------------
# WHERE THE PICKS CAME FROM. The tier constants above grade the ARTIFACT. They
# say nothing about where the pixel coordinates came from, and that gap let this
# file stamp "(Type A, MEASURED)" on a repeatability computed from five
# coordinate pairs typed into `__main__` — a demo constant that reached the
# project's records as a measurement and became a candidate for substitution
# into the uncertainty budget.
#
# The lesson generalises past this file: a provenance system must grade EVERY
# input to a claim, not the most impressive one. So the pick basis is recorded
# beside the artifact tier, and the MEASURED label is derived from it rather
# than written by hand.
# --------------------------------------------------------------------------
PICKS_FROM_DETECTOR = "DETECTED_IN_IMAGE"      # cornerSubPix &c. on real pixels
PICKS_FROM_OPERATOR = "OPERATOR_PICKED_IN_IMAGE"
PICKS_DECLARED_LITERAL = "DECLARED_LITERALS"   # typed in: a worked example
PICKS_UNRECORDED = "NOT_RECORDED"              # nobody said, so assume nothing

# Only these two produce a number that measured anything. The default is
# deliberately NOT in this set: a caller that forgets to say under-claims, which
# is the direction a compliance instrument should fail in.
_PICKS_FROM_AN_IMAGE = frozenset((PICKS_FROM_DETECTOR, PICKS_FROM_OPERATOR))
_PICK_BASES = frozenset((PICKS_FROM_DETECTOR, PICKS_FROM_OPERATOR,
                         PICKS_DECLARED_LITERAL, PICKS_UNRECORDED))


# --------------------------------------------------------------------------
# The handoff. One object crosses from this module into the measurement engine,
# and it carries its own provenance so that a height measured under a printed
# specimen can never be reported as if it were measured under glass.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScaleReference:
    px_per_mm: float
    artifact: ScaleArtifact
    n_frames: int
    rel_sd: float                    # sample sd of px/mm, relative
    recovered_at: float              # time.time(), for staleness
    field_position: str = "centre"   # where in the frame it was recovered
    note: str = ""
    # Where the pixel coordinates came from. See the PICKS_* block above for why
    # this is a separate axis from the artifact tier, and why its default is the
    # one that claims nothing.
    pick_basis: str = PICKS_UNRECORDED

    def __post_init__(self) -> None:
        if self.pick_basis not in _PICK_BASES:
            raise ValueError("unknown pick basis {!r}".format(self.pick_basis))

    @property
    def tier(self) -> str:
        return self.artifact.tier

    @property
    def mm_per_px(self) -> float:
        return 1.0 / self.px_per_mm

    @property
    def picks_measured_an_image(self) -> bool:
        """True only when the picks came off real pixels.

        This is the predicate the MEASURED label is derived from. It exists as a
        property rather than an inline test so that there is exactly one place
        where "this number measured something" is decided.
        """
        return self.pick_basis in _PICKS_FROM_AN_IMAGE

    @property
    def baseline_px(self) -> float:
        """The pixel separation the scale was recovered over.

        Recovered rather than stored, and there is no circularity in doing so
        for a REPORT: px_per_mm was computed as separation / declared pitch, so
        multiplying back is exact. It must not be used as an independent check
        of the separation, because it is not one.
        """
        return self.px_per_mm * self.artifact.pitch_mm

    @property
    def fiducial_term_mm(self) -> float:
        """The fiducial-localisation term at the baseline actually achieved.

        0.2 px on each of two features gives 0.283 px on their separation; as a
        fraction of the achieved baseline that is the term, on a 1 mm glyph.

        The budget carries 0.001 mm, derived at the MIN_BASELINE_PX threshold of
        283 px, which is the worst case this rig should present on a full-span
        read. Above that baseline this number comes out smaller than the budget
        allows, which is the direction that costs nothing. It is printed on every
        manifest rather than left to a warning, so the achieved value is on the
        record even when nothing tripped.
        """
        return _FIDUCIAL_PICK_PX / self.baseline_px

    def type_a_sd_mm(self, height_mm: float = 1.0) -> float:
        """Measured Type A standard uncertainty from scale recovery, in mm.

        READ THIS BEFORE PUTTING THE NUMBER IN THE BUDGET.

        FIRST, CHECK `pick_basis`. This function is arithmetic and will happily
        return a number for coordinates that were typed into a file. It measured
        something only when `picks_measured_an_image` is True. The manifest
        derives its label from that predicate; anyone quoting this number
        elsewhere has to check it by hand, and until a rig session has run the
        honest sentence is "there is no measured repeatability in this project".

        The term is RELATIVE, so it must be quoted against a height; the budget
        is written at a 1 mm glyph, hence the default. It measures REPEATABILITY
        of scale recovery on a static artifact and nothing else. It is blind to
        an error in the declared pitch, to printer inaccuracy, to lens
        distortion, and to any systematic mislocalisation of the feature — all of
        which are biases, and repeatability cannot see a bias.

        It REPLACES the modelled random scale-recovery term in the v7 budget. It
        does not add to it. Identify that term by name in the v7 source before
        substituting: adding a ninth term because the eighth was inconvenient to
        find would inflate U while claiming to have measured something.

        AND THE SUBSTITUTION CAN GO WRONG IN THE FLATTERING DIRECTION, which is
        the direction nobody audits. A measured repeatability will usually come
        out SMALLER than the modelled allowance it replaces, so U drops - on this
        rig, plausibly 0.17 mm to 0.16 mm. That reduction is only legitimate if
        the v7 term was a pure repeatability allowance. If it also stood in for
        declared-pitch error, printer error, or systematic mislocalisation, then
        substituting a repeatability figure does not measure those away; it
        deletes their allowance and calls the result an improvement.

        So: read what the v7 term covers. If it is repeatability alone,
        substitute. If it covers anything else, or the source does not say, KEEP
        the modelled term and report this number beside it as a consistency
        check. Measured repeatability coming out below the modelled allowance is
        evidence the allowance was not optimistic - a real and reportable result,
        and a smaller claim than a smaller U.

        This is nonetheless worth doing, and it is the cheapest honest upgrade
        available: it moves one term of eight from `modelled` to `measured`, on a
        table, in five minutes, with no certified artifact and no micrometer.
        """
        return self.rel_sd * height_mm

    def report_lines(self) -> tuple[str, ...]:
        cert = self.artifact.certificate_id or "none"
        # The label is DERIVED from the pick basis, never written by hand. This
        # line used to read "(Type A, MEASURED)" unconditionally, which is how a
        # repeatability computed from five typed-in coordinate pairs entered this
        # project's records as a measurement.
        if self.picks_measured_an_image:
            tag = "(Type A, MEASURED: picks {})".format(self.pick_basis)
        elif self.pick_basis == PICKS_DECLARED_LITERAL:
            tag = ("(NOT MEASURED: picks are declared literals, so this is a "
                   "worked example of the arithmetic and not a measurement of "
                   "this rig)")
        else:
            tag = ("(NOT MEASURED: pick basis not recorded, so this number "
                   "carries no authority - see PICKS_* in lm_capture)")
        lines = [
            "SCALE REFERENCE        : {:.3f} px/mm".format(self.px_per_mm),
            "  artifact             : {}".format(self.artifact.name),
            "  declared pitch       : {:.4f} mm (DECLARED, not measured here)".format(
                self.artifact.pitch_mm),
            "  authority tier       : {} (certificate: {})".format(self.tier, cert),
            "  pick basis           : {}".format(self.pick_basis),
            "  recovered from       : {} frames at field position {}".format(
                self.n_frames, self.field_position),
            "  repeatability        : {:.3%} relative, = {:.4f} mm on a 1 mm glyph"
            " {}".format(self.rel_sd, self.type_a_sd_mm(1.0), tag),
            # Printed on EVERY manifest rather than left to a warning. The warning
            # covers the case where the term is worse than budgeted; this line
            # states the term that was actually achieved, every time, so the
            # number is on the record whether or not anything went wrong.
            "  fiducial term        : {:.4f} mm on a 1 mm glyph at the achieved"
            " {:.0f} px baseline".format(self.fiducial_term_mm, self.baseline_px),
            "  caveat               : repeatability is not accuracy; no lens model"
            " is applied and no field-position term is measured",
        ]
        # The artifact's own limitation, printed rather than merely stored. The
        # printed target's note says it cannot validate a scale; that sentence is
        # useless sitting in a constant while the manifest reports a tidy px/mm.
        # Same rule as the session notes: an unprinted caveat does not exist.
        if self.artifact.note:
            lines.append("  artifact limitation  : {}".format(self.artifact.note))
        return tuple(lines)


# The scale is recovered once per rig session and re-verified, not re-derived per
# frame. Two reasons, and the second is the one that matters: re-deriving invites
# a silent drift where each frame is measured against a slightly different world,
# and it throws away the between-frame spread, which is the only free measurement
# in the whole budget.
_SCALE_STALE_SECONDS = 45.0 * 60.0


@dataclass
class RigSession:
    """Mutable per-sitting state: the scale, and the focus baseline.

    Deliberately not frozen. This is the one place in the project that models a
    physical sitting rather than a fact, and a sitting changes: somebody nudges
    the camera, the room light changes, the scale is re-taken.
    """

    scale: ScaleReference | None = None
    focus_baseline: float | None = None
    events: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.events.append("{:.3f}  {}".format(time.time(), msg))

    def require_scale(self, now: float | None = None) -> ScaleReference:
        """The chokepoint. Every path to a millimetre goes through here."""
        if self.scale is None:
            raise CaptureRefusal(
                CAP_NO_SCALE_REFERENCE,
                "no scale reference has been established in this session. A "
                "photograph carries pixels; the requirement is in millimetres; "
                "nothing in the image supplies the conversion. Put the "
                "calibration artifact in frame and run a scale session.")
        now = time.time() if now is None else now
        age = now - self.scale.recovered_at
        if age > _SCALE_STALE_SECONDS:
            raise CaptureRefusal(
                CAP_SCALE_STALE,
                "the scale reference is {:.0f} minutes old. On a rig that gets "
                "carried to a demo room, a scale older than {:.0f} minutes is an "
                "assumption, not a measurement. Re-take it.".format(
                    age / 60.0, _SCALE_STALE_SECONDS / 60.0))
        return self.scale


# ==========================================================================
# PURE ARITHMETIC. No camera, no OpenCV, no I/O. Everything that can be tested
# without hardware lives here on purpose — the parts below that touch a device
# are the parts nobody can check until Sunday, so the boundary is drawn to keep
# them as thin as possible.
# ==========================================================================
def scale_from_separation(px_separation: float, artifact: ScaleArtifact) -> float:
    """px/mm from a measured pixel separation between two features of the artifact."""
    if px_separation <= 0.0:
        raise ValueError("px_separation must be positive")
    return px_separation / artifact.pitch_mm


def summarise_scale_samples(samples: "list[float] | tuple[float, ...]"
                            ) -> tuple[float, float]:
    """(mean px/mm, relative sample sd) over repeated recoveries.

    Sample sd with n-1, not n. With twelve frames the difference is 4% in the sd,
    which is small — but the n-1 form is the estimator of a population sd from a
    sample, and this figure is going into an uncertainty budget where using the
    biased form would be a defect of exactly the kind this project logs.

    THIS SD IS NOT A BOUND, so do not pass it to `check_field_uniformity`; that
    gate wants `half_range_rel` below. The arity here stays at two because three
    call sites unpack it, so the bound is a separate function rather than a third
    return value.
    """
    n = len(samples)
    if n < 2:
        raise ValueError("need at least 2 samples to estimate a spread")
    if any(s <= 0.0 for s in samples):
        raise ValueError("px/mm samples must be positive")
    mean = sum(samples) / n
    var = sum((s - mean) ** 2 for s in samples) / (n - 1)
    return (mean, math.sqrt(var) / mean)


def half_range_rel(samples: "list[float] | tuple[float, ...]") -> float:
    """Half the peak-to-peak spread of the samples, as a fraction of their mean.

    A DIFFERENT OBJECT FROM THE SD ABOVE, and the distinction is the whole point.
    `summarise_scale_samples` returns a standard deviation, which answers "how
    much does a fresh sample scatter". This returns a bound, which answers "how
    far from the middle can the recovered scale be anywhere I looked". Feed the
    first into a Type A uncertainty; feed the second into `check_field_uniformity`.

    This exists because the sd was being fed to a gate whose docstring promised a
    bound, and a relative sd over five points is roughly 1/sqrt(3) to 1/2 of the
    half-range for anything resembling a uniform spread - so the gate was passing
    fields whose worst corner was around double what the budget allotted. The
    number here is deliberately the larger, more conservative one.

    IT IS OUTLIER-SENSITIVE and that is a cost, not a hidden virtue: one badly
    localised corner sets the whole figure and can refuse a field that is fine
    everywhere else. For a compliance instrument that is the correct direction to
    fail in - the operator re-seats the artifact and shoots again - but say so out
    loud rather than pretending the statistic is robust. If a refusal looks
    suspicious, print the samples and look at which one is the outlier; do NOT
    respond by moving the gate.

    Two samples make this exactly the sd's own half-range and it is nearly
    meaningless; four or five spread over the artifact's extent is the intended
    use.
    """
    n = len(samples)
    if n < 2:
        raise ValueError("need at least 2 samples to bound a spread")
    if any(s <= 0.0 for s in samples):
        raise ValueError("px/mm samples must be positive")
    mean = sum(samples) / n
    return (max(samples) - min(samples)) / 2.0 / mean


def check_resolution_floor(px_per_mm: float) -> None:
    """Refuse below the engineering floor. Not a warning: below the floor the
    sub-pixel edge model has not been characterised, so the uncertainty budget
    does not describe the measurement being made.

    THIS GATE FIRES FIRST AND IT USED TO GIVE THE WRONG REMEDY. px/mm on the
    two-point path is the picked separation over the artifact's DECLARED pitch, so
    an operator who picks one graduation of a 10 mm graticule instead of its full
    span lands here — 40 px over a declared 10 mm reads as 4 px/mm — and the old
    message told them to move the camera closer, which would not fix it. The two
    explanations are indistinguishable from the number alone, so the message now
    names both and lets the operator look.
    """
    if px_per_mm < MIN_PX_PER_MM:
        raise CaptureRefusal(
            CAP_SCALE_BELOW_FLOOR,
            "recovered {:.1f} px/mm, below the {:.0f} px/mm floor the edge model "
            "was characterised at. Two things produce this and the number cannot "
            "tell them apart. Either the field is too wide - move the camera "
            "closer or crop tighter - or the picked separation was not the "
            "artifact's full declared pitch, because px/mm is separation over "
            "DECLARED pitch and a sub-span pick understates it by exactly the "
            "fraction picked. Check which before moving anything. Note also that "
            "the first case is the tradeoff behind the capability claim: a bigger "
            "panel needs a wider field, and a wider field costs px/mm.".format(
                px_per_mm, MIN_PX_PER_MM))


def check_tier_change(previous: ScaleReference | None,
                      proposed_tier: str,
                      allow_tier_change: bool = False) -> str | None:
    """Guard a mid-session change in scale authority. Returns a log line, or None.

    The hazard is not the change itself — swapping paper for glass halfway
    through is a genuine improvement. The hazard is a change nobody noticed,
    after which "we measured on the rig against a glass artifact" describes some
    of the session and not the rest.

    Nothing is retroactively relabelled: every measurement carries the
    `ScaleReference` it was made under, which is the whole reason that object is
    frozen. So this is a confirmation gate, not a prohibition — deliberately, on
    the reasoning that a guard which merely annoys the operator gets deleted at
    nine on Wednesday morning, and a guard that gets deleted protects nothing.
    """
    if previous is None or proposed_tier == previous.tier:
        return None
    direction = ("UPWARD" if _TIER_RANK[proposed_tier] > _TIER_RANK[previous.tier]
                 else "DOWNWARD")
    if not allow_tier_change:
        raise CaptureRefusal(
            CAP_TIER_CHANGED,
            "this session established scale at tier {} and is now being offered "
            "{} — a {} change in authority. Earlier measurements keep their own "
            "reference and are unaffected, but the session is no longer "
            "describable by one sentence. Pass allow_tier_change=True to make "
            "this a decision rather than an accident.".format(
                previous.tier, proposed_tier, direction))
    return "scale tier changed {} -> {} ({})".format(
        previous.tier, proposed_tier, direction)


def check_scale_stability(rel_sd: float) -> None:
    """Refuse a scale whose repeated recoveries disagree.

    An unstable scale is usually vibration, a loose mount, autofocus hunting, or
    mains flicker beating against the exposure. All four are fixable in a minute
    and all four are invisible in a single frame, which is the argument for
    taking a dozen.
    """
    if rel_sd > SCALE_SPREAD_REJECT_REL:
        raise CaptureRefusal(
            CAP_SCALE_UNSTABLE,
            "scale recovery varied by {:.2%} across frames, above the {:.2%} "
            "limit. Likely causes, cheapest first: autofocus still enabled, a "
            "loose camera mount, table vibration, or mains flicker against the "
            "exposure time. Lock focus and exposure and re-take.".format(
                rel_sd, SCALE_SPREAD_REJECT_REL))


def check_focus(metric: float, baseline: float | None) -> None:
    """Gate, not measurement — and the distinction is the point.

    Variance-of-Laplacian is scene-dependent, so there is no absolute threshold:
    a sharp photograph of a plain box scores lower than a blurred photograph of
    dense text. What is comparable is the same rig, the same session, against a
    baseline taken on the calibration artifact at best focus.

    This does NOT bound the defocus term in the budget, and must never be quoted
    as if it did. Symmetric defocus preserves a 50% intensity crossing exactly,
    which is why that term is 0.005 mm rather than something large; what this
    catches is the gross case where the specimen was placed at a different height
    from the artifact and nobody looked.
    """
    if baseline is None:
        raise CaptureRefusal(
            CAP_NO_FOCUS_BASELINE,
            "no focus baseline for this session. Take one on the calibration "
            "artifact at best focus first; an absolute sharpness threshold is "
            "meaningless because the statistic depends on scene content.")
    if metric < baseline * FOCUS_FLOOR_FRACTION:
        raise CaptureRefusal(
            CAP_FOCUS_INSUFFICIENT,
            "sharpness {:.1f} is below {:.0%} of this session's baseline {:.1f}. "
            "Most likely the specimen is not in the plane the artifact was in. "
            "Re-focus, or shim the specimen to the artifact's height.".format(
                metric, FOCUS_FLOOR_FRACTION, baseline))


# ==========================================================================
# THE DEVICE BOUNDARY. Everything below here talks to OpenCV or a camera, which
# means none of it can be checked without hardware. It is kept thin and kept
# together so that "the untested part" is a nameable region of the file rather
# than a property of the whole thing.
#
# The API surface used is deliberately the oldest and most stable part of cv2:
# VideoCapture, cvtColor, Laplacian, findChessboardCorners, cornerSubPix. No
# aruco (it has moved between contrib versions twice), no DNN, no recent flags.
# ==========================================================================
def _backend():
    """Import cv2 lazily and refuse with a usable message if it is absent.

    Lazy on purpose: the pure functions above, the self-test, and every
    stills-based path must all work on a machine with no OpenCV, because that is
    how the rest of the pipeline gets demonstrated if the rig does not arrive.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise CaptureRefusal(
            CAP_BACKEND_UNAVAILABLE,
            "OpenCV is not importable ({}). Install opencv-python, or run the "
            "stills path instead — the measurement engine does not depend on "
            "this module.".format(exc))
    return cv2


def _grab(cap, cv2, discard: int = 2):
    """One frame, after discarding the first few.

    The discard is not superstition: USB cameras deliver stale buffered frames
    and ramp exposure and gain over the first several frames after opening. A
    scale recovered from frame zero is recovered from a different camera state
    than the specimen is measured in.
    """
    for _ in range(max(0, discard)):
        cap.read()
    ok, frame = cap.read()
    if not ok or frame is None:
        raise CaptureRefusal(
            CAP_NO_FRAME,
            "the camera opened but returned no frame. Check that nothing else "
            "holds the device, and that the index is right.")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def focus_metric(gray) -> float:
    """Variance of the Laplacian. Session-relative only — see `check_focus`."""
    cv2 = _backend()
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def check_baseline_length(sep_px: float) -> str | None:
    """Warn when the scale baseline is shorter than the corrected fiducial term
    assumed, and refuse when it is short enough to be an operator error. Returns a
    warning line, or None.

    THE WARNING IS A WARNING ON PURPOSE, and it used to fire on every correct
    capture, which is worse than useless: an operator who sees the same note on
    every frame stops reading the notes field, and that field is where the honest
    caveats live. The cause was a threshold derived from a 566 px baseline that
    this artifact cannot present in the operating range. See MIN_BASELINE_PX for
    the corrected chain; the short version is that the achievable baseline sets
    the term, not the other way round, and the term went UP as a result.

    WHAT THIS GATE ACTUALLY CATCHES, once the arithmetic is followed through, is
    AN ARTIFACT TOO SHORT TO SUPPORT THE BUDGETED TERM — not an operator's short
    read. The two-point path computes px/mm as separation over DECLARED pitch, so
    separation and px/mm are locked together: sep = px_per_mm x pitch_mm. Any
    session that survives `check_resolution_floor` therefore has
    sep >= 30 x pitch_mm, which is 300 px for the 10 mm graticule and 600 px for
    the 20 mm printed target. Both clear 283 px, so ON THE SHIPPED ARTIFACTS THIS
    WARNING IS STRUCTURALLY SILENT.

    That is the intended state and it is worth being explicit rather than quietly
    pleased about it. The warning band 36-283 px opens only when
    30 x pitch_mm < 283, i.e. for an artifact whose declared span is under about
    9.4 mm. So this is a guard against a future artifact swap - somebody brings a
    5 mm graticule, gets 150 px at the floor, and needs to be told the budget's
    fiducial term no longer covers the geometry. It is not a guard against a
    sub-span read.

    A SUB-SPAN READ IS CAUGHT EARLIER AND HARDER, by `check_resolution_floor`,
    with a refusal rather than a note: one 1 mm graduation of the 10 mm graticule
    read at 40 px/mm gives 40 px, which divided by the declared 10 mm reads as
    4 px/mm. That refusal now names both possible causes, because the number alone
    cannot distinguish "camera too far" from "picked a fraction of the span".

    THE REFUSAL IS A DIFFERENT FAILURE, and it is reachable because it runs before
    the resolution floor: `scale_from_two_points` calls this on the raw separation,
    so a pick under 36 px refuses here with CAP_BASELINE_TOO_SHORT, while anything
    from 36 px up to 30 x pitch_mm refuses later with CAP_SCALE_BELOW_FLOOR. Below
    36 px the pick is a fraction of a millimetre at any working magnification and
    no diagnosis is needed beyond "that is not a measurement". See that constant
    for the derivation, including the admission that the gate is loose.
    """
    if sep_px <= 0.0:
        raise ValueError("sep_px must be positive")
    if sep_px < ABS_MIN_BASELINE_PX:
        raise CaptureRefusal(
            CAP_BASELINE_TOO_SHORT,
            "the scale baseline is {:.0f} px, below the {:.0f} px floor. At any "
            "working magnification that is a fraction of a millimetre, so this is "
            "almost certainly one graduation rather than the artifact's full "
            "span. Read the longest separation the artifact offers.".format(
                sep_px, ABS_MIN_BASELINE_PX))
    if sep_px >= MIN_BASELINE_PX:
        return None
    # The achieved term, computed rather than scaled from a literal, so that this
    # message cannot drift away from `ScaleReference.fiducial_term_mm`.
    achieved = _FIDUCIAL_PICK_PX / sep_px
    budgeted = _FIDUCIAL_PICK_PX / MIN_BASELINE_PX
    return ("scale baseline is {:.0f} px against the {:.0f} px this rig should "
            "reach on a full-span read, so the fiducial term is ~{:.4f} mm on a "
            "1 mm glyph against the {:.4f} mm the budget carries - {:.1f}x. Still "
            "negligible against U = 0.166 mm, so this is a disclosure and not a "
            "crisis; the likely cause is a sub-span read, so check which "
            "separation was picked.".format(
                sep_px, MIN_BASELINE_PX, achieved, budgeted, achieved / budgeted))


def check_field_uniformity(field_bound_rel: float) -> str | None:
    """Refuse a capture whose scale varies across the field by more than the
    budget allows for it. Returns a warning line, or None.

    THE ARGUMENT is a bound on a systematic you have no model for. If the
    calibration artifact carries a repeating feature, the variation in recovered
    scale ACROSS that artifact bounds the sum of residual perspective and lens
    distortion over the region it covers — from data already in the frame, at
    capture time, every time. It cannot separate tilt from distortion and does not
    try; for bounding a systematic, the sum is the right object, and it is a
    measurement rather than an estimate. This is the cheapest real upgrade in the
    module, and it addresses the audit's sharpest finding — that a low reprojection
    residual is not dimensional accuracy and this project has no lens model.

    PASS A BOUND, NOT AN SD. `field_bound_rel` must be a half-range-type figure -
    use `half_range_rel`. The parameter was called `spread_rel` and was being fed a
    relative n-1 standard deviation while this docstring claimed to gate "a
    conservative bound", which is two different objects sharing one name. For five
    samples over a uniform-ish spread the sd runs about 1/sqrt(3) to 1/2 of the
    half-range, so the old gate passed fields whose worst corner was roughly twice
    the budgeted allowance.

    LENS_FIELD_TERM_REL DOES NOT MOVE FOR THIS. Comparing a larger statistic
    against the same limit makes the instrument claim less, not more, so the
    correction cannot be an accommodation to any refusal rate - which is the test
    this project applies to every moved limit. The ~sqrt(3) of extra conservatism
    is deliberate and is the price of not having a lens model.

    Two honest limits survive the fix: it bounds the variation over the ARTIFACT's
    extent, not the whole frame, so it says nothing about a glyph outside that
    region; and it is blind to any error uniform across the field, which is exactly
    what a wrong declared pitch is. Neither limit is a reason to skip it.
    """
    if field_bound_rel < 0.0:
        raise ValueError("field_bound_rel must be non-negative")
    if field_bound_rel > LENS_FIELD_TERM_REL:
        raise CaptureRefusal(
            CAP_FIELD_NONUNIFORM,
            "recovered scale varies by up to {:.2%} across the artifact, above the "
            "{:.2%} the budget allots to field position. The stated U does not "
            "describe this capture. Sit the artifact flat and square to the "
            "sensor, or measure closer to the optical axis. If one sample looks "
            "like an outlier, re-pick it — do not widen the gate.".format(
                field_bound_rel, LENS_FIELD_TERM_REL))
    if field_bound_rel > LENS_FIELD_TERM_REL / 2.0:
        return ("field scale bound {:.2%} is over half the budgeted allowance "
                "{:.2%} — within limits, but it is consuming the term".format(
                    field_bound_rel, LENS_FIELD_TERM_REL))
    return None


def chessboard_scale(gray, inner_cols: int, inner_rows: int,
                     square_mm: float) -> tuple[float, float]:
    """(px/mm, relative field BOUND across the board) from a printed chessboard.

    The board is a SPECIMEN — its true square pitch is whatever the printer did —
    so a scale from here is `SCALE_FROM_SPECIMEN` and cannot validate anything.
    It is here because it is automatic, repeatable, and gives the field bound
    `check_field_uniformity` wants for free; the glass graticule goes through the
    two-point path.

    THE SECOND RETURN IS A HALF-RANGE, NOT AN SD. It used to be the relative n-1
    sd from `summarise_scale_samples`, which was then handed to a gate whose
    docstring promised a bound — the statistic and the specification disagreed.

    IT IS DELIBERATELY CONSERVATIVE, and the reason is worth writing down because
    it looks like a flaw. Each sample here is one adjacent-corner spacing, so it
    carries per-corner localisation noise ON TOP OF the field variation the budget
    term is about. A peak-to-peak therefore bounds noise + systematic rather than
    the systematic alone. That over-states the term, which for a BOUND is the
    correct direction, and the size is small: at 5 mm squares and 30 px/mm a
    spacing is ~150 px, cornerSubPix scatter on a pair is ~0.1 px, so the noise
    floor is ~0.07% relative and its half-range over a few dozen samples is
    ~0.15-0.2% against a 1.00% allowance.

    WHICH MEANS SQUARE SIZE MATTERS MORE THAN IT LOOKS. At 2 mm squares the same
    noise is ~0.17% relative and its half-range alone eats half the allowance, so
    the gate will warn on a board that is optically fine. The fix is a bigger
    board, not a bigger gate. Print 5 mm squares or larger.

    Every spacing is counted once: the two loops below walk horizontal pairs and
    vertical pairs disjointly.
    """
    cv2 = _backend()
    if inner_cols < 2 or inner_rows < 2:
        raise ValueError("need at least a 2x2 inner corner grid")
    if square_mm <= 0.0:
        raise ValueError("square_mm must be positive")
    found, corners = cv2.findChessboardCorners(gray, (inner_cols, inner_rows))
    if not found:
        raise CaptureRefusal(
            CAP_SCALE_AMBIGUOUS,
            "no {}x{} chessboard found. Check the inner-corner count (it is "
            "corners, not squares), the lighting, and that the whole board is in "
            "frame.".format(inner_cols, inner_rows))
    cv2.cornerSubPix(
        gray, corners, (5, 5), (-1, -1),
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001))
    pts = [(float(c[0][0]), float(c[0][1])) for c in corners]
    spacings: list[float] = []
    for r in range(inner_rows):
        for c in range(inner_cols - 1):
            i = r * inner_cols + c
            spacings.append(math.dist(pts[i], pts[i + 1]))
    for r in range(inner_rows - 1):
        for c in range(inner_cols):
            i = r * inner_cols + c
            spacings.append(math.dist(pts[i], pts[i + inner_cols]))
    mean_px, _rel_sd = summarise_scale_samples(spacings)
    return (mean_px / square_mm, half_range_rel(spacings))


def open_camera(index: int = 0, width: int = 1920, height: int = 1080):
    """Open a device with autofocus, auto-exposure and auto-white-balance OFF.

    This is the least glamorous function in the project and one of the most
    important. An autofocusing camera changes its own magnification between the
    scale frame and the specimen frame, which is a scale error with no signature
    in the image — the picture looks fine and the millimetres are wrong. Auto
    exposure moves the ink-to-substrate levels the 50% edge criterion is defined
    against, which moves the measurand itself.

    Every `cap.set` here is a REQUEST. Drivers ignore them silently and
    per-property support varies by camera, OS and backend, so the returned flags
    are checked and reported rather than assumed. If a camera refuses to lock
    focus, that is a fact about the rig which belongs in the manifest, not an
    exception to swallow.
    """
    cv2 = _backend()
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise CaptureRefusal(
            CAP_NO_FRAME,
            "could not open camera index {}. Try another index, and check no "
            "other process holds the device.".format(index))
    requests = (
        ("width", cv2.CAP_PROP_FRAME_WIDTH, float(width)),
        ("height", cv2.CAP_PROP_FRAME_HEIGHT, float(height)),
        ("autofocus off", cv2.CAP_PROP_AUTOFOCUS, 0.0),
        ("auto exposure manual", cv2.CAP_PROP_AUTO_EXPOSURE, 0.25),
        ("auto white balance off", cv2.CAP_PROP_AUTO_WB, 0.0),
    )
    notes: list[str] = []
    for label, prop, value in requests:
        try:
            accepted = bool(cap.set(prop, value))
        except Exception as exc:                     # driver-specific failures
            accepted = False
            notes.append("{}: raised {}".format(label, exc))
        if not accepted:
            notes.append("{}: NOT ACCEPTED by the driver".format(label))
    return cap, tuple(notes)


# Pure, despite sitting below the device boundary: kept next to its caller
# because it is the entire implementation of the manual path, and covered by the
# camera-free self-test.
def scale_from_two_points(p1: tuple[float, float], p2: tuple[float, float],
                          artifact: ScaleArtifact) -> tuple[float, str | None]:
    """(px/mm, baseline warning or None) from two operator-identified features a
    declared distance apart.

    This is the path the glass graticule uses, and the path that will actually be
    used on Wednesday, because it needs no pattern detection and no printed
    target — two graduations and a declared span. Its weakness is honest and
    stated in the manifest: the operator located those two points, so the
    localisation error is human and is not the 0.2 px the budget's fiducial term
    assumes. Take the same pair several times and let the spread say so.
    """
    sep = math.dist(p1, p2)
    if sep <= 0.0:
        raise CaptureRefusal(
            CAP_SCALE_AMBIGUOUS,
            "the two points given are coincident, so they define no separation.")
    return (scale_from_separation(sep, artifact), check_baseline_length(sep))


def _median(values: "list[float]") -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def build_scale_reference(session: RigSession,
                          artifact: ScaleArtifact,
                          samples: "list[float]",
                          field_bound_rel: float | None = None,
                          focus_samples: "list[float] | None" = None,
                          field_position: str = "centre",
                          pick_basis: str = PICKS_UNRECORDED,
                          allow_tier_change: bool = False,
                          extra_notes: "list[str] | None" = None,
                          now: float | None = None) -> ScaleReference:
    """All the gates, in order, then commit the scale to the session.

    Camera-free by design: it takes samples rather than a device, so the entire
    decision logic of the capture path is testable without hardware. The camera
    functions above only produce the numbers this consumes.

    Gate order matters and is the same lesson as the legal layer's check order: a
    scale that is unstable AND below the floor should report the instability,
    because instability is a rig fault the operator can fix in a minute while the
    floor is a geometry decision that may require moving the camera.

    `field_bound_rel` MUST be a half-range-type bound (`half_range_rel`), not an
    sd. `pick_basis` defaults to the value that claims nothing, so a caller who
    forgets under-claims rather than over-claims; see PICKS_* at the top of the
    module for why that default is the safe one.
    """
    change = check_tier_change(session.scale, artifact.tier, allow_tier_change)
    mean_ppm, rel_sd = summarise_scale_samples(samples)
    check_scale_stability(rel_sd)
    check_resolution_floor(mean_ppm)
    warning = None
    if field_bound_rel is not None:
        warning = check_field_uniformity(field_bound_rel)

    notes = []
    # Caveats go on the frozen reference, not only into the session log. A
    # caveat that lives in a log nobody prints is a caveat that does not exist,
    # and the reference is what travels with the measurement.
    if extra_notes:
        notes.extend(extra_notes)
    if change:
        notes.append(change)
        session.log(change)
    if warning:
        notes.append(warning)
        session.log(warning)
    if field_bound_rel is None:
        notes.append("field uniformity not measured on this path (single feature "
                     "pair gives no across-field information)")

    ref = ScaleReference(
        px_per_mm=mean_ppm,
        artifact=artifact,
        n_frames=len(samples),
        rel_sd=rel_sd,
        recovered_at=time.time() if now is None else now,
        field_position=field_position,
        pick_basis=pick_basis,
        note="; ".join(notes),
    )
    if focus_samples:
        # Median, not max. The max is the single sharpest frame, which sets a
        # baseline that most legitimate frames then fail against.
        session.focus_baseline = _median(list(focus_samples))
    session.scale = ref
    session.log("scale committed: {:.3f} px/mm, tier {}, rel sd {:.3%}".format(
        ref.px_per_mm, ref.tier, ref.rel_sd))
    return ref


@dataclass(frozen=True)
class SpecimenCapture:
    """THE HANDOFF. This is the only object that crosses into the measurement
    engine, and it cannot be constructed without a `ScaleReference` — which is
    the structural version of this module's one rule. There is no field for
    "assume 30 px/mm", and adding one would defeat the file.

    `camera_notes` has no default ON PURPOSE. It used to default to `()`, and once
    `capture_specimen` started reading an empty tuple as "every lock request was
    accepted", that default would have made silence into an attestation for anyone
    constructing this object directly. Every caller now has to say something, even
    if what it says is that nothing was recorded.
    """

    gray: object                     # single-channel image, whatever cv2 returned
    scale: ScaleReference
    focus: float
    captured_at: float
    camera_notes: tuple[str, ...]

    @property
    def px_per_mm(self) -> float:
        return self.scale.px_per_mm


def run_chessboard_scale_session(session: RigSession, cap,
                                 artifact: ScaleArtifact,
                                 inner_cols: int, inner_rows: int,
                                 square_mm: float,
                                 frames: int = SCALE_SESSION_FRAMES
                                 ) -> ScaleReference:
    """Automatic path. Repeats the recovery `frames` times on a static artifact
    so that the spread is measured rather than assumed.

    Two different statistics come out of the loop and they must not be confused.
    `ppms` scatter frame-to-frame and their sd becomes the Type A repeatability;
    `bounds` are per-frame field half-ranges and their MEDIAN goes to the field
    gate. Median across frames, not max: one frame with a badly localised corner
    should not set a session-wide bound, and the half-range within a frame is
    already the outlier-sensitive part.

    Picks here are `PICKS_FROM_DETECTOR` — findChessboardCorners plus cornerSubPix
    on real pixels — so the repeatability this path produces is a measurement of
    this rig, and the manifest will say so.
    """
    cv2 = _backend()
    ppms: list[float] = []
    bounds: list[float] = []
    focuses: list[float] = []
    for k in range(frames):
        gray = _grab(cap, cv2, discard=2 if k == 0 else 0)
        ppm, bound = chessboard_scale(gray, inner_cols, inner_rows, square_mm)
        ppms.append(ppm)
        bounds.append(bound)
        focuses.append(focus_metric(gray))
    return build_scale_reference(
        session, artifact, ppms,
        field_bound_rel=_median(bounds),
        pick_basis=PICKS_FROM_DETECTOR,
        focus_samples=focuses)


def capture_specimen(session: RigSession, cap,
                     camera_notes: "tuple[str, ...] | None" = None
                     ) -> SpecimenCapture:
    """One specimen frame, or a refusal. The scale gate runs BEFORE the frame is
    taken: there is no reason to capture a specimen we cannot convert, and a
    frame sitting in a variable is an invitation to measure it anyway.

    `camera_notes=None` MEANS NOBODY ASKED. An empty tuple means `open_camera` was
    asked and every lock request came back accepted. Those are different facts and
    the earlier `camera_notes or (...)` collapsed them, so a caller who passed
    nothing got a manifest asserting "all requested locks accepted" — an
    attestation about hardware nobody had interrogated. The sentinel is the fix:
    the default now claims nothing, which is the same rule as `PICKS_UNRECORDED`.
    """
    ref = session.require_scale()
    cv2 = _backend()
    gray = _grab(cap, cv2)
    metric = focus_metric(gray)
    check_focus(metric, session.focus_baseline)
    session.log("specimen captured at focus {:.1f}".format(metric))
    # Three distinguishable states, deliberately. None: nobody interrogated the
    # camera, so the manifest says exactly that. Empty tuple: open_camera ran and
    # every lock request was accepted - an attestation, and it has to be earned.
    # Non-empty: the driver refused something and here is what.
    if camera_notes is None:
        notes: tuple[str, ...] = (
            "camera lock state NOT recorded - this frame carries no attestation "
            "that focus, exposure or white balance were locked",)
    elif not camera_notes:
        notes = ("all requested locks accepted",)
    else:
        notes = tuple(camera_notes)
    return SpecimenCapture(gray, ref, metric, time.time(), notes)


def manifest_lines(cap_result: SpecimenCapture) -> tuple[str, ...]:
    """The evidence chain, printed. Without this, "we measured it on a rig" is a
    claim; with it, it is a record somebody else could audit or dispute.

    Kept separate from the measurement report on purpose. The measurement report
    says what was found; the manifest says under what conditions, and the two
    have different audiences — the second is the one an inspector's lawyer reads.
    """
    lines = ["CAPTURE MANIFEST"]
    lines.extend("  " + l for l in cap_result.scale.report_lines())
    lines.append("  focus (session-rel)  : {:.1f}".format(cap_result.focus))
    lines.append("  captured at          : {:.3f} epoch".format(
        cap_result.captured_at))
    lines.append("  scale age at capture : {:.1f} s".format(
        cap_result.captured_at - cap_result.scale.recovered_at))
    if cap_result.scale.note:
        lines.append("  scale notes          : {}".format(cap_result.scale.note))
    if cap_result.camera_notes:
        for n in cap_result.camera_notes:
            lines.append("  camera               : {}".format(n))
    else:
        # An empty note list is NOT the same as a clean bill of health. It means
        # this capture did not come through `capture_specimen`, so no lock
        # requests were made or recorded - which is exactly the case for a stills
        # or declared-picks run. `capture_specimen` substitutes an explicit
        # "accepted" note, so the two cases stay distinguishable on the record.
        lines.append("  camera               : lock status not recorded (this "
                     "capture did not come from open_camera)")
    lines.append("  NOT APPLIED          : lens undistortion (no lens model "
                 "exists in this project)")
    return tuple(lines)


def run_two_point_scale_session(
        session: RigSession,
        artifact: ScaleArtifact,
        point_pairs: "list[tuple[tuple[float, float], tuple[float, float]]]",
        pick_basis: str,
        picks_on_one_frame: "bool | None" = None,
        focus_samples: "list[float] | None" = None,
        field_position: str = "centre",
        allow_tier_change: bool = False,
        now: float | None = None) -> ScaleReference:
    """The manual path, end to end, and it needs no camera and no OpenCV.

    `pick_basis` IS REQUIRED AND HAS NO DEFAULT. This is the path the demo runs,
    and on the demo the picks are literals typed into `__main__`, so the caller has
    to say so and the manifest then refuses to stamp MEASURED on arithmetic. Every
    other function in the module defaults this to `PICKS_UNRECORDED`; here a
    default would be the one place the omission actually costs something.

    `picks_on_one_frame` closes a gap this docstring used to describe and the
    signature could not express. The operator identifies the same pair of features
    several times — on ONE frozen frame, or on SUCCESSIVE frames — and the spread
    means different things: on one frame it measures the operator's hand, on
    successive frames it measures the operator plus the rig, which is the larger
    and more honest number. Both are useful; they are not interchangeable, and a
    Type A term quoted without saying which one it is cannot be checked. None means
    nobody recorded it, and the manifest says that rather than guessing.

    Camera-free is not an accident. It means the whole decision path of the
    capture layer runs in the self-test, and it means the demo has a fallback
    that works from a still photograph if the rig fails on the morning.
    """
    if pick_basis not in _PICK_BASES:
        raise ValueError("unknown pick basis {!r}".format(pick_basis))
    if len(point_pairs) < 2:
        raise ValueError(
            "need at least two picks to estimate a spread; one pick gives a "
            "scale with no uncertainty, which is the thing this module exists "
            "to refuse to pretend")
    ppms: list[float] = []
    seps: list[float] = []
    for p1, p2 in point_pairs:
        ppm, _warn = scale_from_two_points(p1, p2, artifact)
        ppms.append(ppm)
        seps.append(math.dist(p1, p2))

    # AGGREGATE, DO NOT DEDUPE. The old loop kept `warn not in warnings`, which
    # deduped on the FORMATTED MESSAGE - and `{:.0f}` collapses five picks of the
    # same span to a handful of distinct strings, so the manifest still carried
    # several near-identical notes saying the same thing about the same baseline.
    # Deduping on a rendered string is not deduping; it is deduping on the
    # rounding. So gate the WORST separation once and report the range.
    notes: list[str] = []
    worst = check_baseline_length(min(seps))
    if worst:
        notes.append("{} (worst of {} picks; picked separations {:.1f}-{:.1f} px)"
                     .format(worst, len(seps), min(seps), max(seps)))
    if picks_on_one_frame is True:
        notes.append("picks taken on ONE frozen frame, so the spread measures the "
                     "operator's repeatability and NOT the rig's")
    elif picks_on_one_frame is False:
        notes.append("picks taken on SUCCESSIVE frames, so the spread measures "
                     "operator plus rig")
    else:
        notes.append("not recorded whether picks came from one frozen frame or "
                     "successive frames, so what the spread measures is unknown")
    for n in notes:
        session.log(n)
    ref = build_scale_reference(
        session, artifact, ppms,
        field_bound_rel=None,
        pick_basis=pick_basis,
        focus_samples=focus_samples,
        field_position=field_position,
        allow_tier_change=allow_tier_change,
        extra_notes=notes,
        now=now)
    return ref


# ==========================================================================
# SELF TEST. Camera-free and OpenCV-free by construction, so it runs anywhere,
# including on the machine where none of this has ever executed. Run it first.
#
# What it can and cannot establish, stated so nobody over-reads a green run: it
# tests the DECISION LOGIC of the capture layer — every gate, every refusal code,
# every arithmetic path, and the structural invariant that a measurement cannot
# be constructed without a scale. It tests nothing about OpenCV, nothing about a
# real camera, and nothing about whether a recovered px/mm is CORRECT. The last
# of those needs the artifact on the stage.
# ==========================================================================
_OBSERVED_CODES: "set[str]" = set()


def _refuses(code: str, fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except CaptureRefusal as exc:
        _OBSERVED_CODES.add(exc.code)
        return exc.code == code
    except Exception:
        return False
    return False


def _raises(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except CaptureRefusal:
        return False        # a refusal is not a programming error; be strict
    except Exception:
        return True
    return False


def _passes(fn, *args, **kwargs):
    """Run something expected to succeed and return its value, or the exception.

    Exists so that a gate which wrongly refuses is REPORTED as a failed check
    rather than crashing the self-test on the way past. A suite that dies at the
    first fault tells you about one fault; this one tells you about all of them,
    which matters on a Tuesday night.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return exc


def _refusal_cause(fn, *args, **kwargs) -> str:
    """The physical cause of the refusal a call produces, or "" if it did not
    refuse. For asserting that a message says the useful thing, not merely that
    the right code came back - a code is a label and the operator reads the
    sentence."""
    try:
        fn(*args, **kwargs)
    except CaptureRefusal as exc:
        _OBSERVED_CODES.add(exc.code)
        return exc.cause
    except Exception:
        return ""
    return ""


def self_test() -> None:
    ran = [0]
    failures: list[str] = []
    _OBSERVED_CODES.clear()      # so a second run measures coverage, not history

    def check(label: str, ok: bool) -> None:
        ran[0] += 1
        if not ok:
            failures.append(label)

    # --- artifacts and tiers -------------------------------------------------
    check("a non-positive pitch is rejected",
          _raises(ScaleArtifact, "x", 0.0, SCALE_FROM_STANDARD))
    check("an unknown tier is rejected",
          _raises(ScaleArtifact, "x", 1.0, "GOLD_PLATED"))
    check("CERTIFIED without a certificate id is rejected",
          _raises(ScaleArtifact, "x", 1.0, SCALE_FROM_CERTIFIED))
    check("CERTIFIED with a certificate id is accepted",
          not _raises(ScaleArtifact, "x", 1.0, SCALE_FROM_CERTIFIED, "NABL/123"))
    check("the printed target is ranked below the glass artifact",
          _TIER_RANK[PRINTED_TARGET_20MM.tier]
          < _TIER_RANK[GLASS_GRATICULE_1MM.tier])
    check("neither shipped artifact claims a certificate",
          GLASS_GRATICULE_1MM.certificate_id is None
          and PRINTED_TARGET_20MM.certificate_id is None)
    # The fallback tier is real and must stay usable: if the graticule is lost on
    # the way to the room, a ruler an operator declares is still a scale, and the
    # honest handling is a low tier on the manifest rather than no measurement.
    _declared_art = _passes(ScaleArtifact, "a ruler, operator-declared span",
                            50.0, SCALE_FROM_DECLARED)
    check("an operator-declared span is constructible",
          isinstance(_declared_art, ScaleArtifact))
    check("operator-declared ranks below every artifact tier",
          _TIER_RANK[SCALE_FROM_DECLARED] == 0)

    # --- arithmetic ----------------------------------------------------------
    check("px/mm is separation over declared pitch",
          abs(scale_from_separation(400.0, GLASS_GRATICULE_1MM) - 40.0) < 1e-9)
    check("a non-positive separation is a programming error, not a refusal",
          _raises(scale_from_separation, 0.0, GLASS_GRATICULE_1MM))
    check("one sample cannot yield a spread",
          _raises(summarise_scale_samples, [40.0]))
    check("a non-positive sample is rejected",
          _raises(summarise_scale_samples, [40.0, -1.0]))
    _sum = _passes(summarise_scale_samples, [40.0, 40.1, 39.9, 40.0])
    _mean, _rel = _sum if isinstance(_sum, tuple) else (0.0, 0.0)
    check("the sample mean is right", abs(_mean - 40.0) < 1e-12)
    # sd with n-1: var = 0.02/3, sd = 0.0816497, relative to 40.0
    check("the spread uses the n-1 sample sd", abs(_rel - 0.00204124) < 1e-7)
    check("the median of an odd count is the middle value",
          _median([3.0, 1.0, 2.0]) == 2.0)
    check("the median of an even count is the mean of the middle pair",
          _median([4.0, 1.0, 2.0, 3.0]) == 2.5)

    # --- gates, at and either side of their limits ---------------------------
    check("the resolution floor passes at exactly the floor",
          _passes(check_resolution_floor, MIN_PX_PER_MM) is None)
    check("just below the floor refuses",
          _refuses(CAP_SCALE_BELOW_FLOOR, check_resolution_floor, 29.9))
    check("stability passes at exactly the limit",
          _passes(check_scale_stability, SCALE_SPREAD_REJECT_REL) is None)
    check("just over the stability limit refuses",
          _refuses(CAP_SCALE_UNSTABLE, check_scale_stability, 0.0041))
    check("focus with no baseline refuses distinctly",
          _refuses(CAP_NO_FOCUS_BASELINE, check_focus, 500.0, None))
    check("focus below 55% of baseline refuses",     # 200 * 0.55 = 110
          _refuses(CAP_FOCUS_INSUFFICIENT, check_focus, 100.0, 200.0))
    check("focus above 55% of baseline passes",
          _passes(check_focus, 120.0, 200.0) is None)
    check("a field bound over the budgeted allowance refuses",
          _refuses(CAP_FIELD_NONUNIFORM, check_field_uniformity, 0.011))
    check("a field bound over half the allowance warns",
          isinstance(_passes(check_field_uniformity, 0.006), str))
    check("a field bound well inside the allowance is silent",
          _passes(check_field_uniformity, 0.004) is None)
    check("a negative field bound is a caller error, not a pass",
          _raises(check_field_uniformity, -0.001))
    # The gate's limit did not move when its statistic changed, which is what
    # makes the correction immune to the "you tuned it" objection.
    check("the field allowance is still 1.00% after the statistic changed",
          abs(LENS_FIELD_TERM_REL - 0.010) < 1e-15)

    # --- a bound is not a standard deviation ---------------------------------
    _hs = [40.0, 40.1, 39.9, 40.0]
    _hr = _passes(half_range_rel, _hs)
    check("the half-range is half the peak-to-peak over the mean",
          isinstance(_hr, float) and abs(_hr - 0.0025) < 1e-9)
    # THE WHOLE REASON THE HELPER EXISTS: on the same samples the bound is the
    # bigger number, so feeding the sd to a gate that wants a bound under-refused.
    check("the bound is larger than the sd on the same samples",
          isinstance(_hr, float) and _hr > summarise_scale_samples(_hs)[1])
    check("identical samples bound to zero",
          _passes(half_range_rel, [40.0, 40.0]) == 0.0)
    check("one sample cannot bound a spread", _raises(half_range_rel, [40.0]))
    check("a non-positive sample is rejected by the bound too",
          _raises(half_range_rel, [40.0, -1.0]))

    # --- the baseline gate, re-derived ---------------------------------------
    # REGRESSION. The warning used to fire at 566 px and so fired on every correct
    # capture; 30 px/mm on the artifact's 10 mm span is 300 px, which is the
    # operating point. An always-on warning trains the operator to ignore the
    # notes field, which is where the honest caveats live.
    check("a full-span read at the resolution floor is silent",
          _passes(check_baseline_length, 300.0) is None)
    check("a long baseline is silent",
          _passes(check_baseline_length, 600.0) is None)
    check("the warning threshold is the achievable baseline, not an assumed one",
          abs(MIN_BASELINE_PX - 283.0) < 1e-12)
    _bl = _passes(check_baseline_length, 200.0)
    check("a short baseline warns and names the baseline this rig should reach",
          isinstance(_bl, str) and "283" in _bl)
    check("a warning about the baseline does not overstate it",
          isinstance(_bl, str) and "negligible" in _bl)
    # WHAT THE WARNING BAND IS FOR, stated as a test so the framing cannot drift
    # again. It is an ARTIFACT-SPAN guard, not a short-read guard: a 5 mm graticule
    # at the resolution floor gives 150 px and needs to be told the budgeted term
    # no longer covers it.
    _small = _passes(check_baseline_length, 150.0)
    check("an artifact too short to support the budgeted term warns",
          isinstance(_small, str))
    check("the warning band opens only under ~9.4 mm of declared span",
          MIN_BASELINE_PX / MIN_PX_PER_MM < 9.44)
    # AND THE COUPLING, which is why the band is silent on what we actually own.
    # px/mm is separation over DECLARED pitch, so a session that survives the
    # resolution floor necessarily has sep >= 30 x pitch_mm.
    check("both shipped artifacts clear the warning band at the resolution floor",
          all(MIN_PX_PER_MM * a.pitch_mm >= MIN_BASELINE_PX
              for a in (GLASS_GRATICULE_1MM, PRINTED_TARGET_20MM)))
    # A one-graduation read is NOT caught here. It reads as 4 px/mm against the
    # declared 10 mm and the resolution floor refuses it, which is the harder and
    # more useful outcome - so assert that too, and assert the message no longer
    # sends the operator to move a camera that may be fine.
    check("40 px warns rather than refuses, so this gate does not own that case",
          isinstance(_passes(check_baseline_length, 40.0), str))
    check("a one-graduation read is refused by the floor, not by the baseline gate",
          _refuses(CAP_SCALE_BELOW_FLOOR, check_resolution_floor,
                   40.0 / GLASS_GRATICULE_1MM.pitch_mm))
    check("the floor refusal names the sub-span pick as a possible cause",
          "sub-span pick" in _refusal_cause(check_resolution_floor, 4.0))
    check("the floor refusal still offers the too-wide-field cause as well",
          "crop tighter" in _refusal_cause(check_resolution_floor, 4.0))
    check("one graduation instead of the full span refuses",
          _refuses(CAP_BASELINE_TOO_SHORT, check_baseline_length, 20.0))

    # --- the two-point path --------------------------------------------------
    _two = _passes(scale_from_two_points, (0.0, 0.0), (300.0, 400.0),
                   GLASS_GRATICULE_1MM)                       # 500 px / 10 mm
    check("the two-point path returns a scale and its caveat together",
          isinstance(_two, tuple) and len(_two) == 2)
    _ppm, _warn = _two if isinstance(_two, tuple) else (0.0, None)
    check("two points give separation over declared pitch", abs(_ppm - 50.0) < 1e-9)
    check("a good baseline comes back with no caveat attached", _warn is None)
    _two_short = _passes(scale_from_two_points, (0.0, 0.0), (120.0, 160.0),
                         GLASS_GRATICULE_1MM)                 # 200 px / 10 mm
    check("the baseline caveat comes back with the scale, not instead of it",
          isinstance(_two_short, tuple) and isinstance(_two_short[1], str))
    check("coincident points refuse rather than divide by zero",
          _refuses(CAP_SCALE_AMBIGUOUS, scale_from_two_points,
                   (10.0, 10.0), (10.0, 10.0), GLASS_GRATICULE_1MM))

    # --- the session chokepoint ---------------------------------------------
    _s = RigSession()
    check("a session with no scale refuses to yield one",
          _refuses(CAP_NO_SCALE_REFERENCE, _s.require_scale))
    _ref = _passes(build_scale_reference, _s, GLASS_GRATICULE_1MM,
                   [40.0, 40.1, 39.9, 40.0],
                   focus_samples=[100.0, 200.0, 300.0], now=1000.0)
    check("the happy path builds a reference", isinstance(_ref, ScaleReference))
    check("the reference carries the mean scale",
          isinstance(_ref, ScaleReference) and abs(_ref.px_per_mm - 40.0) < 1e-12)
    check("the focus baseline is the median, not the sharpest frame",
          _s.focus_baseline == 200.0)
    check("the session now yields the scale it was given",
          _passes(_s.require_scale, 1000.0) is _ref)
    check("a scale older than the staleness window refuses",
          _refuses(CAP_SCALE_STALE, _s.require_scale, 1000.0 + 46 * 60))
    check("the measured Type A term is relative, so it scales with height",
          isinstance(_ref, ScaleReference)
          and abs(_ref.type_a_sd_mm(2.0) - 2.0 * _ref.type_a_sd_mm(1.0)) < 1e-15)

    # GATE ORDER. Samples near 10 px/mm with ~5% spread violate both the floor and
    # the stability limit. The refusal must name the instability: that is a rig
    # fault the operator fixes in a minute, while the floor may mean moving the
    # camera and re-establishing everything. Reporting the expensive fault first
    # would send someone to rebuild the rig over a loose mount.
    check("an unstable, under-resolved scale reports the instability first",
          _refuses(CAP_SCALE_UNSTABLE, build_scale_reference,
                   RigSession(), GLASS_GRATICULE_1MM, [10.0, 10.5, 9.5]))

    # --- mid-session authority changes ---------------------------------------
    check("a first scale is not a tier change",
          _passes(check_tier_change, None, SCALE_FROM_SPECIMEN) is None)
    check("re-taking at the same tier is not a change",
          _passes(check_tier_change, _ref, SCALE_FROM_STANDARD) is None)
    check("an unflagged tier change refuses",
          _refuses(CAP_TIER_CHANGED, check_tier_change, _ref, SCALE_FROM_SPECIMEN))
    check("a flagged change to paper is logged as DOWNWARD",
          "DOWNWARD" in str(_passes(check_tier_change, _ref,
                                    SCALE_FROM_SPECIMEN, True)))
    check("a flagged change to a certified artifact is logged as UPWARD",
          "UPWARD" in str(_passes(check_tier_change, _ref,
                                  SCALE_FROM_CERTIFIED, True)))

    # --- the structural invariant, which is the whole point of the file ------
    _flds = {f.name: f for f in fields(SpecimenCapture)}
    check("a capture has no default scale, so it cannot be built without one",
          _flds["scale"].default is MISSING
          and _flds["scale"].default_factory is MISSING)
    check("a capture cannot be built without the frame's focus either",
          _flds["focus"].default is MISSING)
    check("nothing on a capture could stand in for a measured scale",
          not any(("px" in n or "assum" in n or "default" in n)
                  for n in _flds))
    check("px_per_mm is derived from the reference rather than stored",
          isinstance(SpecimenCapture.px_per_mm, property))

    # --- the manifest, built camera-free (gray is never read by it) ----------
    _cap = SpecimenCapture(None, _ref, 210.0, 1000.0 + 30.0,
                           ("autofocus off: NOT ACCEPTED by the driver",))
    _man = _passes(manifest_lines, _cap)
    _man = _man if isinstance(_man, tuple) else ()
    check("the manifest names the authority tier",
          any(SCALE_FROM_STANDARD in l for l in _man))
    check("the manifest marks the pitch as declared",
          any("DECLARED" in l for l in _man))
    check("the manifest keeps the repeatability-is-not-accuracy caveat",
          any("repeatability is not accuracy" in l for l in _man))
    check("the manifest records what was not applied",
          any("NOT APPLIED" in l and "undistortion" in l for l in _man))
    check("a driver that ignored a lock request is on the record",
          any("NOT ACCEPTED" in l for l in _man))
    check("the manifest reports the scale's age at capture",
          any("scale age at capture" in l for l in _man))
    check("the artifact's own limitation reaches the manifest",
          any("no calibration certificate" in l for l in _man))

    # --- paper must never be reportable as glass -----------------------------
    _ps = RigSession()
    _pref = _passes(build_scale_reference, _ps, PRINTED_TARGET_20MM,
                    [40.0, 40.05, 39.95], now=2000.0)
    _pman = _passes(manifest_lines,
                    SpecimenCapture(None, _pref, 100.0, 2000.0, ()))
    _pman = _pman if isinstance(_pman, tuple) else ()
    check("a paper-derived scale reports its tier as a printed specimen",
          any(SCALE_FROM_SPECIMEN in l for l in _pman))
    check("a paper-derived scale says so in words, not only in a code",
          any("NOT usable for validating the scale" in l for l in _pman))
    # Silence about the camera must not read as a clean bill of health: an empty
    # note list means nobody asked, which is the stills and declared-picks case.
    check("a capture with no camera record says so rather than implying success",
          any("lock status not recorded" in l for l in _pman))
    check("and a capture WITH a camera record does not say that",
          not any("lock status not recorded" in l for l in _man))
    check("a capture cannot be built with a silent camera record either",
          _flds["camera_notes"].default is MISSING
          and _flds["camera_notes"].default_factory is MISSING)

    # --- WHERE THE PICKS CAME FROM -------------------------------------------
    # The defect this section exists for: the manifest printed "(Type A, MEASURED)"
    # unconditionally, so a repeatability computed from five coordinate pairs typed
    # into __main__ entered the project's records as a measurement of a rig. The
    # authority tiers could not catch it because they grade the ARTIFACT.
    check("an unknown pick basis is rejected at construction",
          _raises(ScaleReference, px_per_mm=40.0, artifact=GLASS_GRATICULE_1MM,
                  n_frames=5, rel_sd=0.001, recovered_at=1000.0,
                  pick_basis="MEASURED_ISH"))
    check("the default pick basis is the one that claims nothing",
          _ref.pick_basis == PICKS_UNRECORDED if isinstance(_ref, ScaleReference)
          else False)
    check("an unrecorded pick basis is not reported as measured",
          any("NOT MEASURED" in l and "carries no authority" in l for l in _man))
    check("no manifest line claims MEASURED when the picks are unrecorded",
          not any("Type A, MEASURED" in l for l in _man))

    def _ref_with(basis: str) -> ScaleReference:
        return ScaleReference(px_per_mm=40.0, artifact=GLASS_GRATICULE_1MM,
                              n_frames=5, rel_sd=0.001, recovered_at=1000.0,
                              pick_basis=basis)

    _lit = _ref_with(PICKS_DECLARED_LITERAL).report_lines()
    check("declared literals are reported as a worked example, not a measurement",
          any("NOT MEASURED" in l and "worked example" in l for l in _lit))
    check("declared literals are never labelled MEASURED",
          not any("Type A, MEASURED" in l for l in _lit))
    _det = _ref_with(PICKS_FROM_DETECTOR).report_lines()
    check("detector picks on real pixels ARE reported as measured",
          any("Type A, MEASURED" in l and PICKS_FROM_DETECTOR in l for l in _det))
    _op = _ref_with(PICKS_FROM_OPERATOR).report_lines()
    check("operator picks in an image are measured too, and say which",
          any("Type A, MEASURED" in l and PICKS_FROM_OPERATOR in l for l in _op))
    check("only image-derived picks satisfy the predicate the label reads",
          _ref_with(PICKS_FROM_DETECTOR).picks_measured_an_image
          and _ref_with(PICKS_FROM_OPERATOR).picks_measured_an_image
          and not _ref_with(PICKS_DECLARED_LITERAL).picks_measured_an_image
          and not _ref_with(PICKS_UNRECORDED).picks_measured_an_image)
    check("every manifest names the pick basis explicitly",
          any(l.strip().startswith("pick basis") for l in _lit))

    # --- the achieved fiducial term, printed rather than warned about --------
    check("the baseline is px/mm times the artifact's declared pitch",
          abs(_ref_with(PICKS_FROM_DETECTOR).baseline_px - 400.0) < 1e-9)
    check("the fiducial term follows from the achieved baseline",
          abs(_ref_with(PICKS_FROM_DETECTOR).fiducial_term_mm
              - _FIDUCIAL_PICK_PX / 400.0) < 1e-15)
    check("the achieved term at 40 px/mm is inside the budgeted 0.001 mm",
          _ref_with(PICKS_FROM_DETECTOR).fiducial_term_mm < 0.001)
    check("the fiducial term is on every manifest, not only when it trips",
          any("fiducial term" in l for l in _det))

    # --- the two-point session, which is the path Wednesday runs --------------
    _demo_picks = [((120.0, 400.0), (520.0, 400.0)),
                   ((119.4, 400.3), (520.6, 399.8)),
                   ((120.7, 399.6), (519.2, 400.4)),
                   ((119.9, 400.1), (520.1, 400.2)),
                   ((120.2, 399.9), (519.7, 400.0))]
    check("the demo path has no default pick basis to fall back on",
          _raises(run_two_point_scale_session, RigSession(), GLASS_GRATICULE_1MM,
                  _demo_picks))
    check("an invented pick basis is rejected rather than recorded",
          _raises(run_two_point_scale_session, RigSession(), GLASS_GRATICULE_1MM,
                  _demo_picks, "PROBABLY_FINE"))
    _dref = _passes(run_two_point_scale_session, RigSession(),
                    GLASS_GRATICULE_1MM, _demo_picks,
                    PICKS_DECLARED_LITERAL, now=3000.0)
    check("the demo path builds a reference", isinstance(_dref, ScaleReference))
    _dman = _passes(manifest_lines,
                    SpecimenCapture(None, _dref, 209.0, 3000.0, ()))
    _dman = _dman if isinstance(_dman, tuple) else ()
    # THE REGRESSION. This is the exact line that used to read "(Type A, MEASURED)"
    # on five typed-in coordinate pairs.
    check("the demo's repeatability is not reported as a measurement",
          any("NOT MEASURED" in l and "worked example" in l for l in _dman)
          and not any("Type A, MEASURED" in l for l in _dman))
    check("a full-span demo read raises no baseline note at all",
          not any("px against" in l for l in _dman))

    # AGGREGATION, tested on the artifact-swap case that actually reaches the
    # warning: a 5 mm span at 40 px/mm gives 200 px, under the 283 px threshold.
    _small_art = ScaleArtifact(name="self-test only, 5 mm span",
                               pitch_mm=5.0, tier=SCALE_FROM_SPECIMEN,
                               note="constructed by the self-test")
    _sp = [((0.0, 0.0), (200.0, 0.0)), ((0.0, 0.0), (200.5, 0.0)),
           ((0.0, 0.0), (199.5, 0.0)), ((0.0, 0.0), (200.2, 0.0)),
           ((0.0, 0.0), (199.8, 0.0))]
    _sref = _passes(run_two_point_scale_session, RigSession(), _small_art, _sp,
                    PICKS_FROM_OPERATOR, now=3000.0)
    _snote = _sref.note if isinstance(_sref, ScaleReference) else ""
    # The old loop deduped on the FORMATTED message, and "{:.0f}" collapsed five
    # picks to three distinct strings, so three near-identical notes survived
    # saying the same thing about the same baseline. One note, or the fix did not
    # take.
    check("five short picks produce exactly one baseline note, not several",
          _snote.count("px against") == 1)
    check("the one note reports the range of picks rather than one of them",
          "199.5" in _snote and "200.5" in _snote and "worst of 5 picks" in _snote)
    check("an artifact-swap short baseline is warned about, not refused",
          isinstance(_sref, ScaleReference))

    # WHAT THE SPREAD MEASURES. The docstring asked for this to be recorded and the
    # signature had nowhere to put it, so it was never recorded.
    def _frame_note(flag) -> str:
        r = _passes(run_two_point_scale_session, RigSession(), GLASS_GRATICULE_1MM,
                    _demo_picks, PICKS_FROM_OPERATOR, picks_on_one_frame=flag,
                    now=3000.0)
        return r.note if isinstance(r, ScaleReference) else ""

    check("picks on one frozen frame are recorded as measuring the operator",
          "ONE frozen frame" in _frame_note(True)
          and "NOT the rig" in _frame_note(True))
    check("picks on successive frames are recorded as measuring operator plus rig",
          "SUCCESSIVE frames" in _frame_note(False))
    check("not recording which was done is stated, not guessed",
          "not recorded whether" in _frame_note(None))
    check("the three cases are three different notes",
          len({_frame_note(True), _frame_note(False), _frame_note(None)}) == 3)

    # --- every declared refusal must be a refusal that exists ----------------
    # This check exists because the file failed it. CAP_BASELINE_TOO_SHORT was
    # declared and never raised - a refusal in the vocabulary and not in the
    # behaviour, which is the documentation equivalent of an unimplemented
    # feature listed as built. Either exercise the code or delete it.
    _declared = {v for k, v in globals().items()
                 if k.startswith("CAP_") and isinstance(v, str)}
    _hardware_only = {CAP_BACKEND_UNAVAILABLE, CAP_NO_FRAME}
    _unexercised = _declared - _OBSERVED_CODES - _hardware_only
    check("every refusal code is either exercised here or hardware-only: {}".format(
        sorted(_unexercised)), not _unexercised)
    check("the hardware-only codes are not silently claimed as tested",
          not (_hardware_only & _OBSERVED_CODES))

    # --- every numeric gate must be classified derived or placeholder --------
    # Same shape as the check above, one level up: that one asks whether a
    # declared refusal exists, this one asks whether a number can be defended.
    # It catches the Tuesday-night edit that adds a threshold with no argument,
    # and it catches the reverse - a constant deleted while the ledger keeps
    # asserting a derivation for it.
    # The scan deliberately includes _PRIVATE names. _SCALE_STALE_SECONDS is a
    # gate - it decides a refusal - and skipping it because of a leading
    # underscore would be the same accidental hole this project keeps finding.
    _numeric = {n for n, v in globals().items()
                if n.lstrip("_").isupper()
                and isinstance(v, (int, float)) and not isinstance(v, bool)}
    _unclassified = sorted(_numeric - set(_GATE_PROVENANCE))
    check("every numeric gate is classified derived or placeholder: {}".format(
        _unclassified), not _unclassified)
    _stale_ledger = sorted(set(_GATE_PROVENANCE) - _numeric)
    check("the ledger names no constant that has gone away: {}".format(
        _stale_ledger), not _stale_ledger)
    # Catches a typo'd kind or an empty reason. It does NOT audit whether a
    # reason is any good - no test can - so do not read a pass here as a claim
    # that the derivations were checked.
    check("every ledger entry carries a recognised kind and a reason",
          all(kind in (GATE_DERIVED, GATE_PLACEHOLDER, GATE_NOT_A_GATE)
              and why.strip()
              for kind, why in _GATE_PROVENANCE.values()))
    # If the hard floor ever rises above the warning level the warning becomes
    # unreachable, and every short baseline turns into a refusal - a disclosure
    # silently converted into a rejection.
    check("the hard baseline floor stays below the warning level",
          ABS_MIN_BASELINE_PX < MIN_BASELINE_PX)
    # AND THE INVERSE, which is the defect that actually happened. If the warning
    # level sits above the baseline this rig can present at the resolution floor,
    # the warning fires on every correct capture and stops carrying information.
    # 30 px/mm on the artifact's 10 mm span is 300 px; the threshold must fit under
    # that. This is the assertion that would have caught MIN_BASELINE_PX = 566.
    check("the warning level is reachable-under, not always-on at the floor",
          MIN_BASELINE_PX <= MIN_PX_PER_MM * GLASS_GRATICULE_1MM.pitch_mm)
    # The budgeted fiducial term must not be smaller than what the threshold
    # implies, or the budget is claiming a baseline the gate does not enforce.
    check("the budgeted fiducial term covers the threshold it was derived from",
          _FIDUCIAL_PICK_PX / MIN_BASELINE_PX <= 0.001 + 1e-12)

    print("capture self-test: {} checks, {} failed".format(ran[0], len(failures)))
    for f in failures:
        print("  FAIL  {}".format(f))
    if failures:
        raise AssertionError("{} capture checks failed".format(len(failures)))


# ==========================================================================
# INTEGRATION. Read this before wiring anything, because the wiring is where a
# module like this gets quietly defeated.
#
# THE ONE HANDOFF. Exactly one object crosses out of this file:
#
#     SpecimenCapture(gray, scale, focus, captured_at, camera_notes)
#
# The measurement engine takes its px/mm from `capture.scale.px_per_mm` and from
# nowhere else. It must not accept a px/mm argument with a default, must not fall
# back to MIN_PX_PER_MM, and must not remember the last session's scale. Every one
# of those three is a plausible convenience that reintroduces the exact failure
# this file exists to prevent: a wrong scale is invisible in the output, because
# the edges stay crisp, the verdict still prints, and the budget still looks
# respectable while everything is wrong by a factor nobody can see.
#
# CAUTION ON THE v7 SIDE. The v7 identifiers this integration touches were
# reconstructed from a transcript, not read from the file, and several names that
# appear in that transcript do not exist in v7 at all. Open the real source and
# check the entry point's signature before editing it. This module deliberately
# imports neither v7 nor lm_legal_model: the dependency direction is capture ->
# nothing, so a capture-layer self-test cannot be broken by an unrelated edit.
#
# THE ONE BUDGET CHANGE, AND IT IS A SUBSTITUTION. `ScaleReference.type_a_sd_mm()`
# is a MEASURED Type A term. It REPLACES the modelled random scale-recovery term
# in the v7 budget; it is not a ninth term. Find that term by name first. Adding
# a term because the one it replaces was inconvenient to locate would inflate U
# while claiming to have measured something, which is the failure mode this
# project keeps a list of.
#
# The error in the other direction is likelier and more flattering, so guard it
# harder: the measured repeatability will probably come out below the modelled
# allowance, which drops U from 0.17 to about 0.16 mm. Legitimate only if the v7
# term covered repeatability alone. If it also absorbed declared-pitch error or
# systematic mislocalisation, substituting deletes an allowance rather than
# measuring it. Default to keeping the modelled term and reporting the measured
# one beside it; see `type_a_sd_mm` for the full argument. Everything else in the
# budget stays modelled, and U(k=2) stays quoted at 0.17 mm until a micrometer
# says otherwise.
#
# TWO REPORTS, NOT ONE. `manifest_lines()` prints next to the measurement report
# and never inside it. The measurement report says what was found; the manifest
# says under what conditions, with what authority, and what was not applied. They
# have different audiences and merging them loses the second one.
#
# DO NOT COLLAPSE THE GATES into a single validate(). Each refusal names a
# distinct physical cause with a distinct operator action - re-focus, tighten the
# mount, move the camera, sit the artifact flat, read a longer span. "Capture
# failed" costs the operator the diagnosis and, on stage, reads as a crash rather
# than as a decision.
#
# THE RIG SESSION, in order, once the hardware exists. Nothing below has been
# done, so treat it as a plan and not as a record:
#   1. Mount the camera rigidly. `open_camera()` returns the list of lock
#      requests the driver REFUSED; write that list down, because it is the
#      difference between "autofocus was off" and "we asked for autofocus off".
#   2. Graticule in frame, flat and square. Run `run_two_point_scale_session`
#      with at least five picks of the LONGEST span the artifact offers. The
#      resulting rel_sd is the first measured number in the whole budget.
#      TWO ARGUMENTS ARE PART OF THE PROCEDURE, not boilerplate. `pick_basis` is
#      required and must be PICKS_FROM_OPERATOR on this step, because on the rig
#      the picks come off real pixels and the manifest's MEASURED label is derived
#      from that field alone. And decide BEFORE picking whether the five picks come
#      off one frozen frame or five successive frames, then pass
#      `picks_on_one_frame` to say which: one frame measures the operator's hand,
#      successive frames measure the operator plus the rig. The second is the
#      larger and the honest one for the budget. Deciding afterwards is how a
#      hand-steadiness figure ends up quoted as a rig repeatability.
#   3. Repeat at centre and four corners, passing `field_position`. Feed those
#      five means to `half_range_rel` and pass ITS output to
#      `check_field_uniformity` — a HALF PEAK-TO-PEAK RANGE, never the sd that
#      `summarise_scale_samples` returns. The gate's limit is a bound on the worst
#      corner, and for five samples the sd runs roughly 1/sqrt(3) to 1/2 of the
#      half-range, so feeding it an sd passes fields whose worst corner is about
#      double the allowance. That is the measured bound on residual perspective
#      plus distortion, and it is the answer to "you have no lens model" - a bound
#      rather than a model, stated as such.
#      Five samples bound the field crudely and the gate's docstring says so; if
#      the half-range comes out near the limit, the next move is more positions,
#      not a bigger limit.
#   4. Only then reprint the demo targets at 0.70 / 1.00 / 1.30 mm and exercise
#      the decision bands. Targets before scale is backwards: the bands are in
#      millimetres and until step 2 there are no millimetres.
#
# WHAT THIS FILE DOES NOT DO, so that nobody infers it from the fact that it
# exists: no measurement, no OCR, no panel segmentation, no legal lookup, and no
# lens undistortion. There is no lens model in this project. Inventing one here
# would be an unmeasured correction, which is worse than a disclosed uncalibrated
# lens, and the manifest says so on every capture.
#
# STATUS. Nothing in this file has executed. No camera has been attached, and
# every cv2 call is unverified - which is why they are confined below the device
# boundary and why every decision function above it is camera-free. Run
# `self_test()` first; it needs no hardware and no OpenCV. A green run establishes
# that the logic is right, and nothing whatever about whether a recovered px/mm is
# correct. That needs the artifact on the table.
# ==========================================================================


if __name__ == "__main__":
    self_test()

    # A camera-free walk through the two beats the demo turns on. Both run from
    # declared numbers, which is also the stills fallback if the rig fails on the
    # morning: the refusal is real either way, because it is a decision about
    # whether a conversion exists and not about image quality.
    print()
    print("BEAT 1 - a frame with nothing of known size in it")
    session = RigSession()
    try:
        session.require_scale()
    except CaptureRefusal as exc:
        print("  REFUSED [{}]".format(exc.code))
        print("  {}".format(exc.cause))

    print()
    print("BEAT 2 - the calibration artifact slides into frame")
    # Five picks of the same 10 mm span, in pixels, as an operator would produce.
    # THEY ARE LITERALS. Nobody picked them off an image, which is why the call
    # below has to declare PICKS_DECLARED_LITERAL and why the manifest prints
    # "NOT MEASURED" against the repeatability. That label used to read
    # "(Type A, MEASURED)" and it was wrong: this is a worked example of the
    # arithmetic, not a measurement of any rig.
    picks = [((120.0, 400.0), (520.0, 400.0)),
             ((119.4, 400.3), (520.6, 399.8)),
             ((120.7, 399.6), (519.2, 400.4)),
             ((119.9, 400.1), (520.1, 400.2)),
             ((120.2, 399.9), (519.7, 400.0))]
    ref = run_two_point_scale_session(
        session, GLASS_GRATICULE_1MM, picks,
        pick_basis=PICKS_DECLARED_LITERAL,
        focus_samples=[204.0, 211.0, 208.0], now=time.time())
    # camera_notes=None: no camera was opened, so no lock state was recorded, and
    # the manifest has to say that rather than inherit an empty-tuple attestation.
    capture = SpecimenCapture(None, ref, 209.0, time.time(),
                              ("no camera opened on this path - lock state not "
                               "recorded",))
    for line in manifest_lines(capture):
        print("  " + line)

    print()
    print("  Type A arithmetic on the picks : {:.4f} mm on a 1 mm glyph".format(
        ref.type_a_sd_mm(1.0)))
    print("  NOT A MEASURED REPEATABILITY. The picks above are declared literals,")
    print("  so this number is what the arithmetic does, not what this rig does.")
    print("  Until a rig session with real picks has run, the honest sentence is")
    print("  'there is no measured repeatability in this project'.")
    print("  It is also smaller than the modelled random terms it could replace, so")
    print("  substituting it would lower U - which is the tempting direction and the")
    print("  reason it stays out: repeatability is blind to bias, and a smaller U")
    print("  earned by deleting an allowance is not a better instrument.")
    print("  U(k=2) stays quoted at 0.17 mm.")
    print()
    print("  Nothing above touched a camera. The px/mm is arithmetic on declared")
    print("  picks against a declared span, which is exactly what it would be with")
    print("  the rig attached - the camera's only job is to supply the pixels.")
