"""
lm_legal_model.py — the statutory layer for SIH26034.

WHY THIS IS A SEPARATE MODULE, AND NOT A PATCH INTO lm_metrology_v7.py
----------------------------------------------------------------------
The measurement engine answers one question: how tall is this character, and how
well do we know that? The statutory layer answers a different one: how tall does
the law require it to be, under which instrument, in which bracket, as of when?
Those questions have different failure modes. A measurement fails by being
imprecise; a legal lookup fails by being confidently wrong, which is worse and
much harder to see. Conflating them was the principal finding of the 2026-09-05
corpus audit, so the fix is an actual separation rather than more branches inside
`measure_with_category()`.

Three practical reasons this is a new file:
  * No anchor risk. Patching a 1000-line source I cannot read means guessing at
    `old_string` context; this file matches nothing and so cannot mis-apply.
  * It cannot break the working measurement path. The integration surface is
    three call sites, listed in INTEGRATION at the bottom.
  * It is independently testable, and the boundary semantics below are exactly
    the kind of thing that needs a test rather than a careful read.

STATUS: NOTHING IN THIS FILE HAS BEEN EXECUTED BY ITS AUTHOR.
No Python environment was available (VM_DISK_SPACE_INSUFFICIENT for nine
consecutive sessions). Treat every line as unrun. `self_test()` at the bottom is
the first thing to run, before any integration.

STATUS OF THE DATA: the height table is UNVERIFIED. One cell blocks a verdict
outright and one carries a data-quality flag - see the DISPUTED and CHECK notes
on `_ORDINARY` and `_FORMED`. Note the shape of that sentence: it counts what
this software declines on, not how many cells of the statute are disturbed. The
second is a claim about the Gazette and we cannot make it. Nobody here has read
the amendment or its corrigendum from a primary Gazette source, and the
amendment's own identifier - cited internally as G.S.R. 629(E) - is one our two
audits of the ministry page do not agree on.

WHICH NUMBERS AND WHICH NAMES THIS FILE IS ALLOWED TO PRINT, because the rule is
not obvious and a later edit will get it wrong in one of two directions:
  * A threshold the tool APPLIED is printed, always, with its provenance - the
    notification number included - and an explicit "do not present as settled
    law". Suppressing it would make the verdict uncheckable, which trades one
    honesty problem for a worse one.
  * A threshold the tool DID NOT APPLY is never printed, and neither is the
    notification number. A refusal has no audit trail to protect - there is no
    value to justify - so a candidate value in a refusal message is pure
    assertion. Worse, it asserts that we know what the candidates ARE, and for
    the contested cell we do not: see `internal_note` on the 50-100 cm2 ordinary
    bracket. The identifier fails the same test twice over, being both unbacked
    here and contested between our sources, so refusals name the INSTRUMENT,
    whose title nobody disputes.
Public-facing strings therefore live in `note`; the arithmetic and the citations
that only the team resolving the cell needs live in `internal_note` and in
`Provenance.corrigendum`, neither of which anything prints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# --------------------------------------------------------------------------
# Source tiers. Kept separate from confidence on purpose: where a fact came
# from and how much we trust it are different axes, and collapsing them is how
# an aggregator's transcription ends up quoted as if it were the Gazette.
# --------------------------------------------------------------------------
SOURCE_PRIMARY_GAZETTE = "PRIMARY_GAZETTE"   # egazette.gov.in PDF, read
SOURCE_MINISTRY_PAGE = "MINISTRY_PAGE"       # consumeraffairs.gov.in, read
SOURCE_MINISTRY_BOOK = "MINISTRY_BOOK"       # consolidated book (known stale)
SOURCE_AGGREGATOR = "AGGREGATOR"             # indiacode / taxguru / commercial
SOURCE_UNREAD = "UNREAD"                     # cited but not opened by anyone here

CONF_VERIFIED = "VERIFIED"       # read from a primary source, vintage recorded
CONF_UNVERIFIED = "UNVERIFIED"   # plausible, single non-primary source
CONF_DISPUTED = "DISPUTED"       # sources conflict, or a change we cannot locate


@dataclass(frozen=True)
class Provenance:
    """Where a threshold came from, and how much weight it can carry.

    `notified_on` and `effective_from` are deliberately Optional. A None here is
    not laziness: it records that nobody has read the date off the notification,
    and `legal_blockers()` refuses rather than assuming a rule was in force.
    """

    instrument: str
    notification: str
    notified_on: date | None
    effective_from: date | None
    source_tier: str
    confidence: str
    # TEAM-ONLY, AND NOT BECAUSE IT IS SECRET. This string describes a value
    # change, so it contains candidate millimetres, so printing it would put an
    # unsettled number in front of an audience by the side door. Nothing reads
    # this field; `report_lines` deliberately does not. The temptation a later
    # edit will feel is "provenance should be complete" - it should, and the
    # completeness that matters is source tier and confidence, which ARE
    # printed. A self-test invariant checks that no report line contains this
    # text; if you add it to a report, that test is the thing telling you no.
    corrigendum: str | None = None
    note: str = ""

    def is_in_force(self, as_of: date) -> bool:
        # as_of=None is the documented default for a caller that forgot to
        # declare an inspection date (see lm_metrology_v7.py's integration of
        # this module). "Unknown whether it was in force" is not in force,
        # same as effective_from=None below -- found 2026-09-07 while wiring
        # the integration this function's own docstring specifies, where
        # as_of=None reaching a set effective_from raised TypeError instead of
        # refusing. Comparing None to a date is undefined, not False by
        # convention, so this is a correctness fix, not a style one.
        if as_of is None:
            return False
        if self.effective_from is None:
            return False
        return as_of >= self.effective_from

    # ONE IMPLEMENTATION OF THE CAVEAT, USED BY BOTH PATHS. The marker used to be
    # built inline in `report_lines` and omitted entirely by `resolve_threshold`'s
    # warning, so the same identifier printed with two different caveat levels
    # depending on which function a caller reached - and the self-test pinned only
    # the stricter one. Two copies of a caveat is one caveat and one bug waiting.
    #
    # Both retire themselves the moment `confidence` becomes CONF_VERIFIED, which
    # is the same single act - reading the Gazette PDF - that confirms the number,
    # the identifier and the commencement date together.
    def identifier_for_print(self) -> str:
        """The notification number as it may be printed: never bare while unverified.

        Only ever printed as the audit trail of a threshold that was actually
        APPLIED. On a refusal there is no verdict to justify, so the identifier is
        an unbacked assertion in the most-projected text this module produces; that
        rule is enforced at the call sites, not here.
        """
        if self.confidence == CONF_VERIFIED:
            return self.notification
        return self.notification + " (identifier unconfirmed)"

    def commencement_for_print(self) -> str:
        """The commencement date, carrying its own confidence.

        `notified_on=None` and a hard `effective_from` came from ONE secondary
        source that supports neither better than the other, and this one is
        load-bearing: `is_in_force` tests the inspection date against it. Setting it
        to None would fail closed correctly and take the demo with it, so it stays
        and says what it is. Three separate facts are wanted here - notification
        number, notification date, commencement date - and this prints the two that
        exist plus the absence of the third.
        """
        if self.effective_from is None:
            return "UNREAD - no commencement date has been read from a source"
        stamp = self.effective_from.isoformat()
        if self.confidence == CONF_VERIFIED:
            return stamp
        if self.notified_on is None:
            return (stamp + " (UNVERIFIED, and the NOTIFICATION date behind it has "
                    "not been read at all - both come from the same secondary "
                    "source as the table)")
        return stamp + " (UNVERIFIED: same secondary source as the table)"


# --------------------------------------------------------------------------
# Package categories. These strings must match lm_metrology_v7.py exactly —
# do not "tidy" them, the v7 RuleSet.tables keys are these values.
# --------------------------------------------------------------------------
CATEGORY_GENERAL = "general"
CATEGORY_FORMED = "blown_formed_moulded_embossed_perforated"
CATEGORY_NOT_DECLARED = "not_declared"   # sentinel, parallel to the commodity axis

# Commodity classes drive INSTRUMENT selection, which is a different axis from
# package category. A medical device in an ordinary printed carton is still
# governed by MDR 2017, not by the PCR height table.
COMMODITY_GENERAL = "general"
COMMODITY_MEDICAL_DEVICE = "medical_device"
COMMODITY_NOT_DECLARED = "not_declared"

INSTRUMENT_PCR_2011 = "PCR_2011"
INSTRUMENT_MDR_2017 = "MDR_2017"   # referenced, deliberately NOT implemented

_INSTRUMENT_BY_COMMODITY = {
    COMMODITY_GENERAL: INSTRUMENT_PCR_2011,
    COMMODITY_MEDICAL_DEVICE: INSTRUMENT_MDR_2017,
}


def governing_instrument(commodity_class: str) -> str | None:
    """None means we cannot tell, which is a refusal, not a default to PCR."""
    return _INSTRUMENT_BY_COMMODITY.get(commodity_class)


# DISPLAY TITLES, kept separate from the codes above rather than replacing them.
# The codes are KEYS - v7's RuleSet is keyed on these exact strings, so
# prettifying them breaks the integration - while a refusal is read by a person
# and, in the medical-device demo beat, projected. "governed by MDR_2017" reads
# like a leaked variable name.
#
# TITLES ONLY, AND NEVER A NOTIFICATION NUMBER. That is the whole reason this
# mapping is safe to print in a refusal: which amendment carries the height
# table is contested between our two audits, but what the parent instrument is
# called is not. Neither title below has been read off a Gazette either; a title
# is a name rather than a value, and the PCR title is the wording of the problem
# statement itself. The MDR entry is the reported short title and is not
# load-bearing - a medical device refuses at step 1, before any table lookup.
_INSTRUMENT_TITLES = {
    INSTRUMENT_PCR_2011: "the Legal Metrology (Packaged Commodities) Rules, 2011",
    INSTRUMENT_MDR_2017: "the Medical Devices Rules, 2017",
}


def instrument_title(code: str) -> str:
    """Human-readable name for a refusal message.

    Falls back to the code rather than raising. An unrecognised instrument must
    not turn a legal refusal into a KeyError on stage, and the bare code is
    still true - only ugly.
    """
    return _INSTRUMENT_TITLES.get(code, code)


# --------------------------------------------------------------------------
# The height table.
#
# BRACKET SEMANTICS, stated because getting this wrong is a silent one-cell
# error at exactly the boundary. The source reads:
#     A <= 50, 50 < A <= 100, 100 < A <= 500, 500 < A <= 2500, A > 2500
# so the lower bound is EXCLUSIVE and the upper bound is INCLUSIVE, except the
# first bracket whose lower bound is 0 inclusive. `bracket_for()` implements
# exactly that and `self_test()` pins A = 50.0, 100.0 and 2500.0 explicitly.
# --------------------------------------------------------------------------
_PCR_2017 = Provenance(
    instrument=INSTRUMENT_PCR_2011,
    notification="G.S.R. 629(E)",
    notified_on=None,                    # NOT READ by anyone on this project
    effective_from=date(2018, 1, 1),     # reported as in force 1 Jan 2018
    source_tier=SOURCE_AGGREGATOR,       # indiacode mirror, not the Gazette PDF
    confidence=CONF_UNVERIFIED,
    corrigendum=(
        "A corrigendum to G.S.R. 629(E) is reported to change one table value "
        "from 1.5 to 2.0. WHICH CELL IS UNRESOLVED."
    ),
    note=(
        "effective_from is itself unverified and comes from the same secondary "
        "source as the table. If the table is wrong, this date is wrong too."
    ),
)


@dataclass(frozen=True)
class HeightBracket:
    pdp_area_min_cm2: float          # exclusive, except the first bracket
    pdp_area_max_cm2: float | None   # inclusive; None = unbounded above
    min_height_mm: float
    provenance: Provenance
    disputed: bool = False           # blocks a verdict
    warn: bool = False               # annotates a verdict, does not block
    note: str = ""                   # PUBLIC. Printed in refusals and warnings.
    internal_note: str = ""          # NEVER PRINTED. Team-only working detail.

    def contains(self, pdp_area_cm2: float) -> bool:
        if pdp_area_cm2 <= self.pdp_area_min_cm2 and self.pdp_area_min_cm2 > 0.0:
            return False
        if pdp_area_cm2 < 0.0:
            return False
        if self.pdp_area_max_cm2 is None:
            return True
        return pdp_area_cm2 <= self.pdp_area_max_cm2


# WHY ONE CELL BLOCKS AND ANOTHER ONLY WARNS.
# Both candidate errors bias toward a LOWER threshold, hence toward false
# COMPLIANT, which is the legally safer direction (a false DEFICIENT accuses a
# compliant packer; a false COMPLIANT merely under-enforces). So neither is a
# safety emergency. The distinction is evidential, not directional:
#   * 50-100 ordinary BLOCKS, because the source documents a corrigendum that
#     alters one value in this table and we cannot establish whether this is the
#     cell it alters. Note what that does NOT license: we do not know this
#     bracket's candidate set. Two readings are open and the source supports
#     both. If the quoted table predates its own corrigendum, this cell is the
#     one that moved. If the quoted table is already post-corrigendum, the moved
#     cell now reads its new value and this cell was never touched - in which
#     case the encoded value is simply correct and we are blocking a sound cell.
#     Blocking under an unresolved reading is a conservative choice, not a
#     demonstrated dispute, and the refusal text must say the former.
#   * A > 2500 formed only WARNS, because the concern is a pattern (the two
#     columns collapse where every other row has formed strictly greater) and a
#     suspicion is not a documented conflict.
_ORDINARY = (
    HeightBracket(0.0, 50.0, 1.0, _PCR_2017),
    HeightBracket(
        50.0, 100.0, 1.5, _PCR_2017,
        disputed=True,
        # THE PUBLIC NOTE NAMES NO NOTIFICATION NUMBER, and that is deliberate
        # for the same reason it names no candidate value. This string is the
        # one the operator reads and the one the projector shows during the
        # demo, and a refusal has no audit trail to protect: there is no
        # applied threshold here to justify, so every identifier in this
        # sentence is pure assertion. It would also be an assertion we cannot
        # back - our two audits of the ministry page do not agree on which
        # amendment introduced the panel-area framework, so the number itself
        # is contested, not merely unread. "The amendment that carries this
        # height table" is true under either audit. The number is recorded in
        # `internal_note` and in the brief, where the people who have to go
        # read the Gazette will find it.
        # Note also "is reported to alter" rather than "alters": we have a
        # secondary report OF a corrigendum, not a corrigendum.
        note=(
            "UNRESOLVED: a corrigendum to the amendment that carries this "
            "height table is reported to alter one value in it, nobody here "
            "has read that corrigendum at source, and we cannot establish "
            "whether this bracket is the cell it alters. No verdict is issued "
            "for this bracket. Resolve by reading the amendment and its "
            "corrigendum in the Gazette together and recording both dates."
        ),
        internal_note=(
            "TEAM-ONLY, DO NOT PRINT AND DO NOT SAY ALOUD. The amendment is "
            "cited as G.S.R. 629(E), an identifier our two audits of the "
            "ministry page do not agree on - do not repeat it on stage. The "
            "audit gives 1.5 "
            "for this cell and separately reports a corrigendum changing a "
            "value from 1.5 to 2.0. 1.5 is the only 1.5 in the transcribed "
            "table, which is consistent with EITHER (a) the table predating its "
            "corrigendum, so this cell is really 2.0 - a 33% swing on a very "
            "common package size - OR (b) the table postdating it, so the "
            "changed cell already reads 2.0 elsewhere and the 1.5 described by "
            "the corrigendum was a different cell we transcribed as something "
            "else. Under (b) this cell is fine. Reading (b) is why the public "
            "note names no candidates: 'either 1.5 or 2.0' would assert a "
            "candidate set we cannot establish.\n"
            "ADDED 2026-09-09, evidence not resolution: a THIRD independent "
            "source (a law firm's dated, detailed analysis, legalculinary.com, "
            "2024-09-13) transcribes the full table with every other cell "
            "matching this one exactly, AND shows A<=50/formed already at "
            "2.0 -- consistent with reading (b), since a table already "
            "carrying the corrected value elsewhere is what postdating the "
            "corrigendum would look like. This favours (b) over (a) but does "
            "not settle it: that source does not itself discuss a corrigendum "
            "or flag any dispute in this table at all, so its silence could "
            "equally mean 'this was never contested' rather than 'the correction "
            "is already applied here.' Two secondary sources agreeing is still "
            "not the Gazette. disputed stays True."
        ),
    ),
    HeightBracket(100.0, 500.0, 2.5, _PCR_2017),
    HeightBracket(500.0, 2500.0, 4.0, _PCR_2017),
    HeightBracket(2500.0, None, 6.0, _PCR_2017),
)

_FORMED = (
    HeightBracket(0.0, 50.0, 2.0, _PCR_2017),
    HeightBracket(50.0, 100.0, 3.0, _PCR_2017),
    HeightBracket(100.0, 500.0, 4.0, _PCR_2017),
    HeightBracket(500.0, 2500.0, 6.0, _PCR_2017),
    HeightBracket(
        2500.0, None, 6.0, _PCR_2017,
        warn=True,
        note=(
            "CHECK: this is the only bracket where the ordinary and formed "
            "columns carry the same value. The applied threshold is reported "
            "above; treat it as provisional until the table is read at source."
        ),
        internal_note=(
            "Column ratios run 2x, 2x, 1.6x, 1.5x, 1x down the table, which is "
            "consistent with the formed column capping at 6.0 mm - so probably "
            "real. It is also exactly what a carried-down transcription error "
            "looks like. Kept as a warning, not a block: a suspicion about a "
            "pattern is not a documented conflict. (The 1.5x here is a ratio "
            "between columns, not a threshold in millimetres.)"
        ),
    ),
)


@dataclass(frozen=True)
class HeightTable:
    category: str
    brackets: tuple[HeightBracket, ...]

    def bracket_for(self, pdp_area_cm2: float) -> HeightBracket | None:
        for b in self.brackets:
            if b.contains(pdp_area_cm2):
                return b
        return None


@dataclass(frozen=True)
class LegalRuleSet:
    """Hashable on purpose, like v7's RuleSet. Tuples, not dicts, for that reason."""

    instrument: str
    tables: tuple[HeightTable, ...]

    def table_for(self, category: str) -> HeightTable | None:
        for t in self.tables:
            if t.category == category:
                return t
        return None

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(t.category for t in self.tables)


PCR_2011 = LegalRuleSet(
    instrument=INSTRUMENT_PCR_2011,
    tables=(
        HeightTable(CATEGORY_GENERAL, _ORDINARY),
        HeightTable(CATEGORY_FORMED, _FORMED),
    ),
)

# --------------------------------------------------------------------------
# The letters-vs-numerals axis is DELIBERATELY ABSENT, and that is a decision
# rather than an omission.
#
# The corpus audit reports the table as governing "numerals and letters"
# together, and advises removing the separate glyph-class axis we had planned.
# We have NOT deleted the idea, because that advice is a claim that something
# does not exist, sourced from secondary material, which is the weakest possible
# warrant for removing a planned feature. It is absent from the DATA because we
# have no second table to put here, and present in this comment because if a
# primary source turns out to carry one, `HeightTable.category` is the axis it
# slots into with no structural change.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# THE LEGAL-UNCERTAINTY GATE.
#
# The measurement engine already declines when the MEASUREMENT is indeterminate
# (REQUIRES_PHYSICAL_VERIFICATION). This is the same idea applied to the law: a
# verdict is blocked by any unresolved legal input, because a threshold you had
# to guess at makes the uncertainty budget behind it irrelevant.
#
# Note the THREE distinct refusal semantics, which must never be merged:
#   MEASURAND_UNDEFINED   - the requirement APPLIES and is knowable, our
#                           instrument cannot find an edge (relief/embossed
#                           characters). Lives in lm_metrology_v7.py, already
#                           correct there.
#   RULESET_NOT_APPLICABLE - a DIFFERENT instrument governs (medical devices ->
#                           MDR 2017). The PCR height table does not apply.
#   THRESHOLD_DISPUTED    - the requirement applies AND the character is
#                           measurable; we do not know the number. This is the
#                           only one of the three where the failure is ours as
#                           readers of the statute rather than as builders of an
#                           instrument, and it is the one that says the LAW is
#                           indeterminate rather than the pixels.
# Telling an inspector an embossed pack is "not applicable" would say the law
# imposes no height requirement on it. That is false, and it is the one place in
# this design where a sloppy label causes real under-enforcement.
# --------------------------------------------------------------------------
BLOCK_COMMODITY_NOT_DECLARED = "COMMODITY_CLASS_NOT_DECLARED"
BLOCK_COMMODITY_UNKNOWN = "COMMODITY_CLASS_UNKNOWN"
BLOCK_RULESET_NOT_APPLICABLE = "RULESET_NOT_APPLICABLE"
BLOCK_CATEGORY_NOT_DECLARED = "CATEGORY_NOT_DECLARED"   # same string as v7
BLOCK_CATEGORY_UNKNOWN = "CATEGORY_UNKNOWN"
BLOCK_PDP_AREA_NOT_DECLARED = "PDP_AREA_NOT_DECLARED"
BLOCK_PDP_AREA_IMPLAUSIBLE = "PDP_AREA_IMPLAUSIBLE"
BLOCK_PDP_AREA_OUT_OF_TABLE = "PDP_AREA_OUT_OF_TABLE"
BLOCK_RULE_VERSION_UNRESOLVED = "RULE_VERSION_UNRESOLVED"
# Deliberate asymmetry, do not "fix" it in either direction: the CODE says
# DISPUTED because it is a stable identifier already referenced in the deck, the
# brief and the integration notes, and churning it four days from the gate buys
# a shade of meaning at the cost of three documents. The MESSAGE says
# "cannot establish", because that is the claim we can actually defend - the
# sources conflict, but we cannot localise the conflict to this cell.
BLOCK_THRESHOLD_DISPUTED = "THRESHOLD_DISPUTED"

# EVERY BLOCK CODE THIS MODULE CAN EMIT, as data. Not a new code - a container of
# the ten above, and it exists for one job: to recognise when one of them has been
# handed BACK to us as an input.
#
# `BLOCK_CATEGORY_NOT_DECLARED` is deliberately the same string as v7's refusal
# code, and that shared string is a trap. The category branch used to accept the
# code itself as a valid "not declared", which silently converted a WIRING FAULT -
# somebody passing the measurement layer's refusal where a package category was
# expected - into a routine non-declaration, destroying the distinction the branch
# beside it exists to preserve. A value nobody supplied and a refusal code
# arriving in a data slot are not the same event and must not print the same
# sentence.
_BLOCK_CODES = frozenset((
    BLOCK_COMMODITY_NOT_DECLARED, BLOCK_COMMODITY_UNKNOWN,
    BLOCK_RULESET_NOT_APPLICABLE, BLOCK_CATEGORY_NOT_DECLARED,
    BLOCK_CATEGORY_UNKNOWN, BLOCK_PDP_AREA_NOT_DECLARED,
    BLOCK_PDP_AREA_IMPLAUSIBLE, BLOCK_PDP_AREA_OUT_OF_TABLE,
    BLOCK_RULE_VERSION_UNRESOLVED, BLOCK_THRESHOLD_DISPUTED))

# A panel larger than this is almost certainly a units error (m2 entered as cm2).
#
# This is the one engineering gate in an otherwise statutory file, so record what
# kind of number it is - the same discipline lm_capture.py applies in
# _GATE_PROVENANCE. It is CHOSEN, but the choice is insensitive and that is the
# argument for it: the two populations it separates are four orders of magnitude
# apart. The table's top bracket already begins at 2500 cm2, and the error being
# caught multiplies by 10,000, so any bound between the largest real retail panel
# and the smallest plausible units error does the same work. 10 m2 sits in the
# middle of that gap.
#
# It is generous on purpose, and the asymmetry is the reason. A false refusal here
# blocks a verdict on a legitimate package. Letting a genuinely enormous area
# through costs nothing, because the lookup returns the top bracket either way.
# So do NOT tighten this to make a refusal rate look better: tightening trades a
# harmless outcome for a harmful one, and the number was never the point.
_PDP_AREA_SANITY_MAX_CM2 = 100_000.0


@dataclass(frozen=True)
class LegalBlocker:
    code: str
    cause: str

    def __str__(self) -> str:
        return "{}: {}".format(self.code, self.cause)


@dataclass(frozen=True)
class ThresholdResolution:
    """The result of asking the law a question. Either a threshold or a reason not."""

    threshold_mm: float | None
    bracket: HeightBracket | None
    blockers: tuple[LegalBlocker, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.threshold_mm is not None and not self.blockers


def resolve_threshold(
    *,
    commodity_class: str,
    package_category: str,
    pdp_area_cm2: float | None,
    as_of: date,
    ruleset: LegalRuleSet = PCR_2011,
) -> ThresholdResolution:
    """Resolve the statutory minimum height, or say precisely why we cannot.

    Check order is deliberate and must not be rearranged: a typo'd category
    should report CATEGORY_UNKNOWN, not a downstream PDP complaint. This is the
    same ordering lesson as v7.1's measurand gate, which had to fire after the
    unknown-category check for exactly this reason.
    """
    blockers: list[LegalBlocker] = []
    warnings: list[str] = []

    # 1. Which instrument governs at all?
    if commodity_class == COMMODITY_NOT_DECLARED:
        blockers.append(LegalBlocker(
            BLOCK_COMMODITY_NOT_DECLARED,
            "commodity class was not declared, so the governing instrument is "
            "unknown; PCR 2011 must not be assumed",
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    instrument = governing_instrument(commodity_class)
    if instrument is None:
        # NOT the same code as the branch above. A value that was never supplied
        # and a value that was supplied and is not recognised are different
        # operator errors: one needs a declaration, the other needs a correction.
        blockers.append(LegalBlocker(
            BLOCK_COMMODITY_UNKNOWN,
            "unrecognised commodity class {!r}; known classes are {}".format(
                commodity_class, ", ".join(sorted(_INSTRUMENT_BY_COMMODITY))),
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    if instrument != ruleset.instrument:
        blockers.append(LegalBlocker(
            BLOCK_RULESET_NOT_APPLICABLE,
            "commodity class {!r} is governed by {}, not by {}. The height "
            "requirement exists but comes from a different instrument, which "
            "this tool does not implement. This is NOT the same as saying no "
            "height requirement applies.".format(
                commodity_class, instrument_title(instrument),
                instrument_title(ruleset.instrument)),
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    # 2. Which column of the table?
    #
    # ONLY the sentinel and an empty value count as "not declared". This branch
    # used to also accept `BLOCK_CATEGORY_NOT_DECLARED` - its own refusal code -
    # which meant a caller who wired v7's refusal string into this argument got a
    # tidy "category was not declared" instead of being told they had passed a
    # refusal where a category belongs. Accepting your own error code as input is
    # how a wiring fault becomes invisible.
    if not package_category or package_category == CATEGORY_NOT_DECLARED:
        blockers.append(LegalBlocker(
            BLOCK_CATEGORY_NOT_DECLARED,
            "package category was not declared; ordinary and formed columns "
            "differ by up to 2x, so this cannot be defaulted",
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    # A refusal code arriving in a data slot is a WIRING FAULT, and it is reported
    # as an unknown category - which is what it is - with a message that names the
    # actual mistake instead of describing the value. No new blocker code: the
    # differential diagnosis belongs in the sentence the operator reads, exactly as
    # the capture layer's resolution floor now distinguishes a too-wide field from
    # a sub-span pick without adding a gate.
    if package_category in _BLOCK_CODES:
        blockers.append(LegalBlocker(
            BLOCK_CATEGORY_UNKNOWN,
            "{!r} is a REFUSAL CODE, not a package category. Something upstream "
            "passed a refusal into the category argument instead of handling it, "
            "so no verdict is possible and this is a wiring fault rather than a "
            "missing declaration - do not read it as 'category not declared'. "
            "Known categories are {}".format(
                package_category, ", ".join(ruleset.categories)),
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    table = ruleset.table_for(package_category)
    if table is None:
        blockers.append(LegalBlocker(
            BLOCK_CATEGORY_UNKNOWN,
            "no table for category {!r}; known categories are {}".format(
                package_category, ", ".join(ruleset.categories)),
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    # 3. Which row? PDP area is a DECLARED input. Determining it from the image
    #    needs panel segmentation, shape classification and the 40% formulae for
    #    cylindrical and irregular packages - that is the expensive half and it
    #    is deliberately not attempted here. An operator declares it or we refuse.
    if pdp_area_cm2 is None:
        blockers.append(LegalBlocker(
            BLOCK_PDP_AREA_NOT_DECLARED,
            "principal display panel area was not declared. The threshold is a "
            "function of it, ranging 1.0 to 6.0 mm, so no verdict is possible",
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    if pdp_area_cm2 <= 0.0 or pdp_area_cm2 > _PDP_AREA_SANITY_MAX_CM2:
        blockers.append(LegalBlocker(
            BLOCK_PDP_AREA_IMPLAUSIBLE,
            "declared PDP area {} cm2 is outside 0 < A <= {:.0f}; check for a "
            "units error (m2 entered as cm2)".format(
                pdp_area_cm2, _PDP_AREA_SANITY_MAX_CM2),
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    bracket = table.bracket_for(pdp_area_cm2)
    if bracket is None:
        blockers.append(LegalBlocker(
            BLOCK_PDP_AREA_OUT_OF_TABLE,
            "declared PDP area {} cm2 fell through every bracket, which means "
            "the table data is malformed, not that the package is unusual".format(
                pdp_area_cm2),
        ))
        return ThresholdResolution(None, None, tuple(blockers), tuple(warnings))

    # 4. Was the rule in force on the inspection date? A notification exists is
    #    not the same as a rule is active: the 2022 unit-sale-price provision was
    #    deferred seven times. An unknown effective date is a refusal, never an
    #    assumption that the rule applied.
    prov = bracket.provenance
    if not prov.is_in_force(as_of):
        # NAME THE INSTRUMENT, NOT THE NOTIFICATION. Same rule as the disputed
        # bracket's public note: this is a refusal, so there is no applied
        # threshold whose audit trail needs the notification number, and the
        # number is contested between our two audits while the instrument's
        # title is not. `prov.instrument` says which rulebook was consulted,
        # which is what the operator needs, and asserts nothing we cannot back.
        if prov.effective_from is None:
            cause = ("no commencement date has been read for the amendment "
                     "carrying this table under {}, so we cannot say it was in "
                     "force on {}".format(instrument_title(prov.instrument), as_of))
        else:
            cause = ("the amendment carrying this table under {} is recorded as "
                     "commencing {} and the inspection date is {}".format(
                         instrument_title(prov.instrument),
                         prov.effective_from, as_of))
        blockers.append(LegalBlocker(BLOCK_RULE_VERSION_UNRESOLVED, cause))
        return ThresholdResolution(None, bracket, tuple(blockers), tuple(warnings))

    # 5. Do we actually know the number in this cell?
    #    Wording matters here. "The threshold is disputed" claims we know there
    #    is a conflict in THIS cell; what we know is weaker - we cannot establish
    #    which cell the corrigendum touched. And `bracket.note` is used rather
    #    than `internal_note` on purpose: this string reaches the operator, the
    #    report and, during the demo, the projector.
    if bracket.disputed:
        blockers.append(LegalBlocker(
            BLOCK_THRESHOLD_DISPUTED,
            "we cannot establish the statutory minimum for this bracket. "
            "{}".format(bracket.note),
        ))
        return ThresholdResolution(None, bracket, tuple(blockers), tuple(warnings))

    if bracket.warn:
        warnings.append("threshold carries a data-quality flag. {}".format(bracket.note))
    if prov.confidence != CONF_VERIFIED:
        # The identifier carries the same marker here as on the applied-report
        # path, from the same method, because a caller can reach either one and
        # two caveat levels on one string is a defect however carefully each is
        # written. The commencement date is named too: it is load-bearing - step 4
        # above tested the inspection date against it - and it is no better sourced
        # than the threshold this warning is about.
        warnings.append(
            "threshold {} mm is {} at source tier {} ({}). Commencement: {}. Do "
            "not present it as settled law.".format(
                bracket.min_height_mm, prov.confidence, prov.source_tier,
                prov.identifier_for_print(), prov.commencement_for_print()))

    return ThresholdResolution(
        bracket.min_height_mm, bracket, tuple(blockers), tuple(warnings))


# --------------------------------------------------------------------------
# The measurement convention is OURS, the requirement is the statute's. Printing
# them on one line implies the law defines a 50% intensity crossing. It does not,
# as far as anyone here has read, and quietly borrowing the statute's authority
# for our own convention is the exact overclaim this project keeps retracting.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MeasurementConvention:
    edge_criterion: str = "50% of the ink-to-substrate intensity transition"
    vertical_extent: str = "cap height: tallest ink extent, descenders excluded"
    declared_by: str = "this instrument"
    statutory_definition_read: bool = False

    def report_lines(self, threshold_mm: float | None,
                     res: ThresholdResolution) -> tuple[str, ...]:
        prov = res.bracket.provenance if res.bracket else None
        lines = []
        if threshold_mm is None:
            lines.append("STATUTORY REQUIREMENT  : unresolved")
        else:
            lines.append("STATUTORY REQUIREMENT  : minimum height {:.1f} mm".format(
                threshold_mm))
            if res.bracket is not None:
                lo = res.bracket.pdp_area_min_cm2
                hi = res.bracket.pdp_area_max_cm2
                # The first bracket's lower bound is INCLUSIVE of zero, every
                # other lower bound is exclusive. Printing "0.0 < A <= 50.0"
                # would misstate the rule on the commonest bracket we show.
                if lo <= 0.0:
                    span = "A <= {} cm2".format(hi)
                elif hi is None:
                    span = "A > {} cm2".format(lo)
                else:
                    span = "{} < A <= {} cm2".format(lo, hi)
                lines.append("  bracket              : {}".format(span))
        if prov is not None:
            # The notification number is printed ONLY when a threshold was
            # actually applied, because that line is the audit trail for the
            # verdict - suppress it and the verdict stops being checkable.
            # A refusal has no verdict to justify, so on that path the same
            # string is an unbacked assertion in the most-projected text this
            # module produces, and it is contested besides: our two audits of
            # the ministry page disagree about which amendment this is. So a
            # refusal names the instrument, which no one disputes.
            #
            # When it IS printed it carries a marker, because the identifier is
            # no better sourced than the number beside it - same secondary
            # transcription. The marker keys off `confidence` rather than a new
            # flag on purpose, and that is not a convenience coupling: one act,
            # opening the Gazette PDF, confirms the identifier and the table
            # values together, so one flag should retire both caveats at the
            # same moment and this line goes clean by itself.
            if threshold_mm is None:
                lines.append("  instrument           : {} [{} / {}]".format(
                    instrument_title(prov.instrument), prov.source_tier,
                    prov.confidence))
            else:
                lines.append("  source               : {} [{} / {}]".format(
                    prov.identifier_for_print(), prov.source_tier,
                    prov.confidence))
            lines.append("  in force from        : {}".format(
                prov.commencement_for_print()))
        lines.append("MEASUREMENT CONVENTION : {} ({})".format(
            self.edge_criterion, self.vertical_extent))
        lines.append("  declared by          : {}; statutory definition read: {}".format(
            self.declared_by, "yes" if self.statutory_definition_read else "NO"))
        return tuple(lines)


DEFAULT_CONVENTION = MeasurementConvention()


# --------------------------------------------------------------------------
# Width. Declared, not implemented. The point of naming it is that a system
# claiming to check the statutory dimensional requirement cannot silently mean
# "the half of it we built".
#
# Why it is not a weekend's work: the width rule carries per-glyph exceptions,
# so applying it requires knowing WHICH character you are looking at. Our
# pipeline locates edges without identifying glyphs, so width makes OCR
# load-bearing inside the dimensional check rather than beside it - a different
# architecture, a new uncertainty term, and its own validation set.
# --------------------------------------------------------------------------
WIDTH_CHECK_IMPLEMENTED = False
WIDTH_RULE_NOTE = (
    "A minimum width relative to height is reported to exist, with exceptions "
    "for certain glyphs. Neither the fraction nor the exception list has been "
    "read from a primary source. NOT IMPLEMENTED, NOT ESTIMATED, NOT CLAIMED."
)


def width_check_status() -> str:
    return "CharacterWidthCheck : NOT IMPLEMENTED - {}".format(WIDTH_RULE_NOTE)


# --------------------------------------------------------------------------
# Relative capability across the table. U is fixed by the instrument, so the
# indeterminate band shrinks as a FRACTION of the threshold as the threshold
# grows. This is the honest framing of our weakest number: the 1 mm case is the
# WORST cell in the table, and it applies only to panels of 50 cm2 or less.
#
# CAVEAT THAT MUST TRAVEL WITH THIS: it holds at CONSTANT px/mm. A large panel
# either needs a wider field, which lowers px/mm and inflates U, or a
# crop-and-stitch capture. The benefit is real on a fixed rig measuring a crop;
# it is not free, and quoting it without the caveat would be a new overclaim.
# --------------------------------------------------------------------------
def relative_capability(U_mm: float, threshold_mm: float) -> tuple[float, float]:
    """Return (indeterminate band as fraction of TL, smallest callable shortfall)."""
    if threshold_mm <= 0.0:
        raise ValueError("threshold must be positive")
    return (2.0 * U_mm / threshold_mm, U_mm / threshold_mm)


def capability_table(U_mm: float,
                     include_disputed: bool = False
                     ) -> tuple[tuple[float, float, float], ...]:
    """(threshold, band fraction, smallest callable shortfall) for every distinct
    threshold in the ruleset. Feed this to the deck rather than retyping numbers.

    `include_disputed` defaults to False so that a disputed cell's value cannot
    reach an outward-facing document through this path. Right now that suppresses
    exactly one row, TL = 1.5 mm, which is the 50-100 cm2 ordinary cell: printing
    a capability figure for it would put the unsettled number on a slide by the
    side door, which the whole design is trying to avoid.
    """
    seen: list[float] = []
    for t in PCR_2011.tables:
        for b in t.brackets:
            if b.disputed and not include_disputed:
                continue
            if b.min_height_mm not in seen:
                seen.append(b.min_height_mm)
    out = []
    for tl in sorted(seen):
        band, shortfall = relative_capability(U_mm, tl)
        out.append((tl, band, shortfall))
    return tuple(out)


# --------------------------------------------------------------------------
# SELF TEST. Run this first; it has never been executed.
# The bracket-boundary cases are the point. An off-by-one at exactly A = 50.0 or
# A = 100.0 is invisible in normal use and wrong on precisely the specimens a
# judge would pick.
# --------------------------------------------------------------------------
_AS_OF = date(2026, 9, 9)


def _resolve(cat=CATEGORY_GENERAL, area=40.0, commodity=COMMODITY_GENERAL,
             as_of=_AS_OF) -> ThresholdResolution:
    return resolve_threshold(commodity_class=commodity, package_category=cat,
                             pdp_area_cm2=area, as_of=as_of)


def _codes(res: ThresholdResolution) -> tuple[str, ...]:
    return tuple(b.code for b in res.blockers)


def self_test() -> None:
    failures: list[str] = []
    ran = [0]

    def check(name: str, cond: bool) -> None:
        ran[0] += 1
        if not cond:
            failures.append(name)

    # Bracket boundaries, ordinary column.
    check("A=50.0 is the first bracket (A<=50)", _resolve(area=50.0).threshold_mm == 1.0)
    check("A=49.9 -> 1.0", _resolve(area=49.9).threshold_mm == 1.0)
    check("A=50.1 falls in the disputed cell",
          _codes(_resolve(area=50.1)) == (BLOCK_THRESHOLD_DISPUTED,))
    check("A=100.0 is still the disputed cell",
          _codes(_resolve(area=100.0)) == (BLOCK_THRESHOLD_DISPUTED,))
    check("A=100.1 -> 2.5", _resolve(area=100.1).threshold_mm == 2.5)
    check("A=500.0 -> 2.5", _resolve(area=500.0).threshold_mm == 2.5)
    check("A=500.1 -> 4.0", _resolve(area=500.1).threshold_mm == 4.0)
    check("A=2500.0 -> 4.0", _resolve(area=2500.0).threshold_mm == 4.0)
    check("A=2500.1 -> 6.0", _resolve(area=2500.1).threshold_mm == 6.0)

    # Formed column. The dispute is in the ordinary column ONLY, so the formed
    # 50-100 cell must still resolve. If this fails, the flag leaked across rows.
    check("formed A=50 -> 2.0", _resolve(CATEGORY_FORMED, 50.0).threshold_mm == 2.0)
    check("formed A=50.1 -> 3.0 and resolves",
          _resolve(CATEGORY_FORMED, 50.1).threshold_mm == 3.0)
    check("formed A=3000 resolves but warns",
          _resolve(CATEGORY_FORMED, 3000.0).threshold_mm == 6.0
          and len(_resolve(CATEGORY_FORMED, 3000.0).warnings) >= 2)

    # Legal blockers. Each must produce its OWN code, because "we refused" is not
    # useful to an operator; "you did not declare the panel area" is.
    check("medical device -> RULESET_NOT_APPLICABLE",
          _codes(_resolve(commodity=COMMODITY_MEDICAL_DEVICE))
          == (BLOCK_RULESET_NOT_APPLICABLE,))
    check("undeclared commodity -> COMMODITY_CLASS_NOT_DECLARED",
          _codes(_resolve(commodity=COMMODITY_NOT_DECLARED))
          == (BLOCK_COMMODITY_NOT_DECLARED,))
    check("misspelt commodity -> COMMODITY_CLASS_UNKNOWN, not NOT_DECLARED",
          _codes(_resolve(commodity="genral")) == (BLOCK_COMMODITY_UNKNOWN,))
    check("undeclared category -> CATEGORY_NOT_DECLARED",
          _codes(_resolve(cat=CATEGORY_NOT_DECLARED)) == (BLOCK_CATEGORY_NOT_DECLARED,))
    check("empty category -> CATEGORY_NOT_DECLARED",
          _codes(_resolve(cat="")) == (BLOCK_CATEGORY_NOT_DECLARED,))
    check("misspelt category -> CATEGORY_UNKNOWN, not a PDP complaint",
          _codes(_resolve(cat="genral")) == (BLOCK_CATEGORY_UNKNOWN,))
    # THE CROSS-MODULE TRAP. v7's refusal code is the same string as this module's
    # blocker code, and this branch used to accept it as a valid "not declared".
    check("a refusal code in the category slot is NOT read as 'not declared'",
          _codes(_resolve(cat=BLOCK_CATEGORY_NOT_DECLARED))
          == (BLOCK_CATEGORY_UNKNOWN,))
    check("and the operator is told it is a wiring fault, not a missing field",
          "REFUSAL CODE" in _resolve(cat=BLOCK_CATEGORY_NOT_DECLARED)
          .blockers[0].cause
          and "wiring fault" in _resolve(cat=BLOCK_CATEGORY_NOT_DECLARED)
          .blockers[0].cause)
    check("every block code is caught in that slot, not just the shared one",
          all(_codes(_resolve(cat=c)) == (BLOCK_CATEGORY_UNKNOWN,)
              for c in _BLOCK_CODES))
    check("the guard list is the ten codes this module can emit and no more",
          len(_BLOCK_CODES) == 10
          and all(isinstance(c, str) and c.isupper() for c in _BLOCK_CODES))
    check("the sentinel and the code are different strings, which is why the "
          "trap existed", CATEGORY_NOT_DECLARED != BLOCK_CATEGORY_NOT_DECLARED)
    check("undeclared PDP area -> PDP_AREA_NOT_DECLARED",
          _codes(_resolve(area=None)) == (BLOCK_PDP_AREA_NOT_DECLARED,))
    check("A=0 -> PDP_AREA_IMPLAUSIBLE (caught before bracket lookup)",
          _codes(_resolve(area=0.0)) == (BLOCK_PDP_AREA_IMPLAUSIBLE,))
    check("A negative -> PDP_AREA_IMPLAUSIBLE",
          _codes(_resolve(area=-40.0)) == (BLOCK_PDP_AREA_IMPLAUSIBLE,))
    check("A=1e6 (m2 entered as cm2) -> PDP_AREA_IMPLAUSIBLE",
          _codes(_resolve(area=1_000_000.0)) == (BLOCK_PDP_AREA_IMPLAUSIBLE,))

    # Check ORDER. A misspelt category with a bad area must complain about the
    # category, because that is the error the operator can act on first.
    check("category error outranks area error",
          _codes(_resolve(cat="genral", area=0.0)) == (BLOCK_CATEGORY_UNKNOWN,))
    check("commodity error outranks category error",
          _codes(_resolve(cat="genral", commodity=COMMODITY_NOT_DECLARED))
          == (BLOCK_COMMODITY_NOT_DECLARED,))

    # Commencement. An inspection predating the rule cannot be judged by it.
    check("inspection in 2017 -> RULE_VERSION_UNRESOLVED",
          _codes(_resolve(as_of=date(2017, 6, 1))) == (BLOCK_RULE_VERSION_UNRESOLVED,))
    check("inspection on the commencement date itself resolves",
          _resolve(as_of=date(2018, 1, 1)).threshold_mm == 1.0)
    check("the day before commencement does not",
          _codes(_resolve(as_of=date(2017, 12, 31)))
          == (BLOCK_RULE_VERSION_UNRESOLVED,))

    # Invariants that must hold while the table is unverified. If either of these
    # starts failing, someone has quietly promoted secondary data to VERIFIED
    # without reading a Gazette PDF, and the whole honesty story goes with it.
    check("no resolved threshold is presented without a warning",
          all(r.resolved and len(r.warnings) >= 1 for r in (
              _resolve(area=40.0), _resolve(area=200.0),
              _resolve(CATEGORY_FORMED, 40.0))))
    check("_PCR_2017 is still UNVERIFIED", _PCR_2017.confidence == CONF_UNVERIFIED)
    check("_PCR_2017 commencement date is still unread",
          _PCR_2017.notified_on is None)
    check("blocked results never carry a threshold",
          all(r.threshold_mm is None for r in (
              _resolve(area=50.1), _resolve(area=None),
              _resolve(commodity=COMMODITY_MEDICAL_DEVICE))))
    check("a blocked result is never reported as resolved",
          not _resolve(area=50.1).resolved and _resolve(area=40.0).resolved)
    check("the first bracket prints its inclusive lower bound correctly",
          any("A <= 50.0 cm2" in l for l in DEFAULT_CONVENTION.report_lines(
              _resolve(area=40.0).threshold_mm, _resolve(area=40.0))))

    # Hashability, because v7's RuleSet is hashable and the report path may key
    # on it. A dict field would have made this raise instead of fail a test.
    try:
        hash(PCR_2011)
        hash(_ORDINARY[0])
        hash(_PCR_2017)
        check("ruleset is hashable", True)
    except TypeError as exc:
        check("ruleset is hashable ({})".format(exc), False)

    # Capability. These are the numbers the deck quotes, so derive them, never
    # retype them. U = 0.16634 mm from the eight-term budget.
    cap = dict((tl, sf) for tl, _band, sf in capability_table(0.16634))
    check("worst cell is TL=1.0", min(cap) == 1.0)
    check("TL=1.0 shortfall is ~16.6%", abs(cap[1.0] - 0.16634) < 1e-9)
    check("TL=6.0 shortfall is ~2.8%", abs(cap[6.0] - 0.16634 / 6.0) < 1e-9)
    check("capability improves monotonically with TL",
          all(cap[a] > cap[b] for a, b in zip(sorted(cap), sorted(cap)[1:])))
    check("the disputed 1.5 mm cell does not reach the deck path", 1.5 not in cap)
    check("1.5 appears only when explicitly asked for",
          1.5 in dict((tl, sf) for tl, _b, sf in capability_table(0.16634, True)))
    check("relative_capability rejects TL<=0", _raises(relative_capability, 0.16634, 0.0))

    # THE LEAK TEST, and it is the one most likely to start failing after a
    # well-meaning edit. Everything above keeps the unsettled value out of the
    # capability path; this keeps it out of the strings a human reads. The demo
    # deliberately triggers the disputed refusal on stage, so its text is the
    # single most-projected string this module produces.
    #
    # Scoped to disputed brackets only. An APPLIED threshold must keep printing:
    # a report that hides the number it adjudicated against is unauditable.
    _disputed = tuple(b for t in PCR_2011.tables for b in t.brackets if b.disputed)
    check("there is exactly one disputed bracket", len(_disputed) == 1)
    _ident_bits = ("G.S.R", "GSR", "629")
    for _b in _disputed:
        _candidates = ("1.5", "2.0", "1.5 mm", "2.0 mm")
        check("a disputed bracket's PUBLIC note names no candidate value",
              not any(c in _b.note for c in _candidates))
        check("a disputed bracket's public note does not say 'disputed'",
              "disput" not in _b.note.lower())
        # The identifier is the same failure one level up: unbacked in a refusal
        # AND contested between our two audits of the ministry page. It is not
        # deleted, only moved, because whoever goes to the Gazette needs it.
        check("a disputed bracket's public note names no notification number",
              not any(i in _b.note for i in _ident_bits))
        check("the team-only reasoning is still recorded somewhere",
              "1.5" in _b.internal_note and "2.0" in _b.internal_note)
        check("the notification number is still recorded team-only",
              any(i in _b.internal_note for i in _ident_bits))
    _blocked = _resolve(area=75.0, cat=CATEGORY_GENERAL)
    check("the disputed bracket does block at A=75", not _blocked.resolved)
    check("its blocker is THRESHOLD_DISPUTED",
          BLOCK_THRESHOLD_DISPUTED in _codes(_blocked))
    check("the refusal message the operator sees names no candidate value",
          not any(c in " ".join(str(b) for b in _blocked.blockers)
                  for c in ("1.5", "2.0")))
    check("the refusal message the operator sees names no notification number",
          not any(i in " ".join(str(b) for b in _blocked.blockers)
                  for i in _ident_bits))
    check("a refused resolution prints 'unresolved', not a number",
          any("unresolved" in l for l in DEFAULT_CONVENTION.report_lines(
              _blocked.threshold_mm, _blocked)))
    # The report is a second printing path and it was leaking after the blocker
    # text was cleaned: a refusal still carries its bracket, so the provenance
    # line still rendered the notification. Testing the strings a human reads
    # rather than the strings a function returns is the difference between
    # catching that and not.
    _blocked_report = DEFAULT_CONVENTION.report_lines(
        _blocked.threshold_mm, _blocked)
    # The sentinel keeps this honest if someone sets `corrigendum=None`: no text
    # means no leak, so the check should PASS, not blow up on `None in str`. A
    # test that crashes instead of failing tells you nothing about the other
    # checks behind it.
    _corr = _PCR_2017.corrigendum or "\x00"
    check("a refusal report names the instrument, not the notification",
          any("instrument" in l for l in _blocked_report)
          and not any(i in l for l in _blocked_report for i in _ident_bits))
    check("no line of a refusal report carries a candidate value",
          not any(c in l for l in _blocked_report for c in ("1.5", "2.0")))
    check("the corrigendum text reaches no report line",
          all(_corr not in l for l in _blocked_report))
    check("an APPLIED threshold is still printed with its value",
          any("2.5 mm" in l for l in DEFAULT_CONVENTION.report_lines(
              _resolve(area=200.0).threshold_mm, _resolve(area=200.0))))
    # And the other direction, which is the half a leak test usually forgets:
    # over-suppression is also a defect. An applied threshold must keep its
    # notification, marked, or the verdict is unauditable.
    _applied_report = DEFAULT_CONVENTION.report_lines(
        _resolve(area=200.0).threshold_mm, _resolve(area=200.0))
    check("an applied threshold still prints its notification",
          any(i in l for l in _applied_report for i in _ident_bits))
    check("and prints it marked as unconfirmed while confidence is not VERIFIED",
          any("identifier unconfirmed" in l for l in _applied_report))
    check("the corrigendum text reaches no applied report line either",
          all(_corr not in l for l in _applied_report))
    # THE OTHER PRINTING PATH. `resolve_threshold`'s own warning carried the same
    # identifier BARE while the report carried it marked, and only the report was
    # pinned - so a caller reading warnings got the weaker caveat and no test knew.
    _warn_text = " ".join(_resolve(area=200.0).warnings)
    check("the warning path prints the identifier marked, like the report does",
          any(i in _warn_text for i in _ident_bits)
          and "identifier unconfirmed" in _warn_text)
    check("the warning path also names the commencement date as unverified",
          "2018-01-01" in _warn_text and "UNVERIFIED" in _warn_text)
    check("one method builds the marker, so the two paths cannot drift again",
          _PCR_2017.identifier_for_print().endswith("(identifier unconfirmed)")
          and _PCR_2017.identifier_for_print().startswith(_PCR_2017.notification))
    check("a blocked resolution's warnings name no notification number",
          not any(i in " ".join(_blocked.warnings) for i in _ident_bits))
    # The commencement date is load-bearing and was the one input asserted as hard
    # fact. It stays - setting it to None fails closed and takes the demo with it -
    # and it now says whose fact it is, including that the notification date behind
    # it was never read at all.
    check("the commencement line says the date is unverified",
          any("in force from" in l and "UNVERIFIED" in l for l in _applied_report))
    check("and says the notification date behind it is unread",
          any("in force from" in l and "not been read" in l
              for l in _applied_report))
    check("an unread commencement date would print UNREAD, not a blank",
          "UNREAD" in Provenance(
              instrument=INSTRUMENT_PCR_2011, notification="x",
              notified_on=None, effective_from=None,
              source_tier=SOURCE_UNREAD,
              confidence=CONF_UNVERIFIED).commencement_for_print())
    check("a VERIFIED provenance would print both clean, retiring both caveats",
          Provenance(instrument=INSTRUMENT_PCR_2011, notification="x",
                     notified_on=date(2017, 6, 23), effective_from=date(2018, 1, 1),
                     source_tier=SOURCE_PRIMARY_GAZETTE,
                     confidence=CONF_VERIFIED).identifier_for_print() == "x"
          and Provenance(instrument=INSTRUMENT_PCR_2011, notification="x",
                         notified_on=date(2017, 6, 23),
                         effective_from=date(2018, 1, 1),
                         source_tier=SOURCE_PRIMARY_GAZETTE,
                         confidence=CONF_VERIFIED).commencement_for_print()
          == "2018-01-01")
    # The commencement refusal is the third path that used to name the number,
    # and it is easy to miss because it is not the demo path. Same rule: no
    # threshold was applied, so it names the instrument.
    _stale = _resolve(as_of=date(2017, 6, 1))
    check("the commencement refusal names no notification number",
          not any(i in " ".join(str(b) for b in _stale.blockers)
                  for i in _ident_bits))
    check("the commencement refusal still says which rulebook was consulted",
          instrument_title(INSTRUMENT_PCR_2011)
          in " ".join(str(b) for b in _stale.blockers))
    # Titles, not keys. `INSTRUMENT_*` are v7 RuleSet keys and they read like
    # leaked variable names on a projector, which is where this text goes.
    _mdr = _resolve(commodity=COMMODITY_MEDICAL_DEVICE)
    _mdr_text = " ".join(str(b) for b in _mdr.blockers)
    check("the medical-device refusal names both instruments by title",
          "Medical Devices Rules, 2017" in _mdr_text
          and "Packaged Commodities" in _mdr_text)
    check("no refusal text exposes a raw instrument key",
          not any(k in t for k in (INSTRUMENT_PCR_2011, INSTRUMENT_MDR_2017)
                  for t in (_mdr_text, " ".join(str(b) for b in _stale.blockers),
                            " ".join(str(b) for b in _blocked.blockers))))
    check("an unknown instrument code falls back to itself, it does not raise",
          instrument_title("NO_SUCH_INSTRUMENT") == "NO_SUCH_INSTRUMENT")
    check("internal_note is never reachable through a blocker or a warning",
          all(_b.internal_note not in " ".join(
              tuple(str(x) for x in _blocked.blockers) + _blocked.warnings)
              for _b in _disputed))

    # Reporting: the requirement and our convention must be separate lines.
    res = _resolve(area=200.0)
    lines = DEFAULT_CONVENTION.report_lines(res.threshold_mm, res)
    check("requirement and convention are separate lines",
          any(l.startswith("STATUTORY REQUIREMENT") for l in lines)
          and any(l.startswith("MEASUREMENT CONVENTION") for l in lines))
    check("report says the statutory definition is unread",
          any("statutory definition read: NO" in l for l in lines))
    check("width is reported as not implemented",
          "NOT IMPLEMENTED" in width_check_status() and not WIDTH_CHECK_IMPLEMENTED)

    print("legal model self-test: {} checks, {} failed".format(ran[0], len(failures)))
    for f in failures:
        print("  FAIL  {}".format(f))
    if failures:
        raise AssertionError("{} legal-model checks failed".format(len(failures)))


def _raises(fn, *args) -> bool:
    try:
        fn(*args)
    except Exception:
        return True
    return False


# ==========================================================================
# INTEGRATION into lm_metrology_v7.py
#
# READ THIS FIRST: the v7 source is not on the disk this file was written on, so
# every v7 identifier named below is reconstructed from transcript and MUST be
# checked against the real source before editing. Do not trust these names. What
# is reliable here is the SHAPE of the three call sites, not their spelling.
#
# The order matters: apply the v7.1 patch and run its regression list BEFORE
# wiring any of this in. Two unvalidated changes at once and you cannot tell
# which one broke the measurement.
#
# CALL SITE 1 - the threshold lookup. This is the substantive change.
#   v7 currently carries a flat rule model: 1.0 mm ordinary, 2.0 mm formed, as
#   constants inside its RuleSet/HeightRule objects. That model is now known to
#   be wrong in general - it is the A <= 50 cm2 row of a five-row table and
#   nothing else. Replace the constant lookup with:
#
#       from lm_legal_model import resolve_threshold, PCR_2011
#       res = resolve_threshold(commodity_class=..., package_category=...,
#                               pdp_area_cm2=..., as_of=inspection_date)
#       if not res.resolved:
#           return <refusal carrying [str(b) for b in res.blockers]>
#       TL = res.threshold_mm
#
#   Note what this does to the demo: the rendered targets become declared
#   small-PDP specimens where TL = 1.0 mm is genuinely correct, so nothing built
#   so far is invalidated. "PDP area 40 cm2 -> bracket A <= 50 -> TL = 1.0 mm"
#   is a better thing to show than a hardcoded constant.
#
# CALL SITE 2 - the measurement entry point gains three arguments:
#       measure_with_category(..., pdp_area_cm2, commodity_class, as_of)
#   All three are DECLARED inputs, none are inferred from the image. Default them
#   to None / COMMODITY_NOT_DECLARED / None rather than to plausible values: a
#   caller that forgets to pass them must get a refusal, not a guess. The legal
#   gate runs BEFORE any pixel work - there is no point measuring a specimen we
#   cannot adjudicate, and a refusal that arrives after the measurement invites
#   somebody to use the measurement anyway.
#
# CALL SITE 3 - the report. Add two blocks:
#       for line in DEFAULT_CONVENTION.report_lines(res.threshold_mm, res):
#           print(line)
#       print(width_check_status())
#   plus res.warnings verbatim. The convention lines must stay separate from the
#   requirement line; that separation is the point of the function.
#
# PRECEDENCE, DECIDED - because `CATEGORY_NOT_DECLARED` is deliberately the same
# string in both modules and "whichever fires first" is not a design.
#   THIS MODULE OWNS THE NOT-DECLARED REFUSAL. The package category is a LEGAL
#   input: its only job is to select a column of the height table, so the layer
#   that owns the table owns the complaint when it is missing. Wire call site 2 so
#   the legal gate runs before any pixel work and v7's own not-declared branch
#   becomes unreachable in the integrated program.
#   DO NOT DELETE v7's BRANCH. It is the second line of defence for anyone calling
#   v7 directly, and deleting a guard because a caller upstream should have caught
#   it is how the guard's absence gets discovered in front of an audience. Comment
#   it as unreachable-when-integrated instead, and if a rehearsal ever sees v7's
#   text, that is a wiring bug and not a difference of opinion between modules.
#   THE MEASURAND GATE STAYS AFTER BOTH. `MEASURAND_UNDEFINED` for relief or
#   embossed characters is CONDITIONAL on knowing the category, so it cannot
#   sensibly precede the declaration of one - the same ordering lesson
#   `legal_blockers` records for its own unknown-category check. Order:
#   category declared -> category recognised -> can we measure this surface ->
#   threshold.
#   AND A REFUSAL CODE IS NOT A CATEGORY. If v7's refusal string arrives in
#   `package_category`, this module reports CATEGORY_UNKNOWN and says in the
#   message that it is a wiring fault. It used to accept the code as a valid "not
#   declared", which turned a broken integration into a routine-looking refusal.
#
# WHAT NOT TO DO
#   * Do not merge MEASURAND_UNDEFINED (v7, embossed: requirement applies, our
#     instrument cannot measure it) into RULESET_NOT_APPLICABLE (here, medical
#     devices: a different instrument governs). Telling an inspector an embossed
#     pack is "not applicable" says the law imposes no height requirement on it.
#     That is false and it is the one label in this design that causes real
#     under-enforcement.
#   * Do not infer pdp_area_cm2 from the image to make the pipeline feel
#     automatic. Panel segmentation plus the 40% cylindrical/irregular formulae
#     is a separate project with its own uncertainty.
#   * Do not promote _PCR_2017.confidence to CONF_VERIFIED until someone has the
#     Gazette PDF of G.S.R. 629(E) and its corrigendum open side by side, and has
#     recorded both dates. Two self-test invariants exist to catch this.
#   * Do not put the 50-100 cm2 ordinary threshold on a slide in either form.
#     Four paths used to leak it and all four are now closed: `capability_table`
#     skips disputed rows, the `__main__` banner no longer names the omitted
#     value, the refusal message is built from the value-free `note`, and the
#     arithmetic moved to `internal_note`, which nothing prints. A block of
#     self-test checks guards all four. If one of them starts failing, the fix is
#     the code, not the check.
#   * Do not put the NOTIFICATION NUMBER in a refusal either, and note that this
#     was found three paths deep after the value leak was called closed: the
#     disputed bracket's public `note`, the commencement refusal's cause, and
#     `report_lines`, which still rendered provenance for a refusal because a
#     refusal carries its bracket. All three now name `prov.instrument`. The
#     lesson is worth more than the fix: cleaning the string a function RETURNS
#     does not clean the string a human READS, so the leak tests assert on
#     rendered report lines, not just on blocker text.
#     The identifier stays printed for an APPLIED threshold, marked "(identifier
#     unconfirmed)" while confidence is not VERIFIED, and a check asserts that
#     too - over-suppression is also a defect, because a verdict whose source is
#     hidden cannot be audited.
#   * Do not "simplify" `note` and `internal_note` back into one field. The
#     split is the mechanism, not decoration: the demo triggers this refusal on
#     stage, so `note` is projected text.
# ==========================================================================


if __name__ == "__main__":
    self_test()
    print()
    print("CAPABILITY ACROSS THE TABLE, U(k=2) = 0.16634 mm, at CONSTANT px/mm")
    print("  TL(mm)   indeterminate band   smallest callable shortfall")
    for tl, band, shortfall in capability_table(0.16634):
        print("  {:5.1f}   {:16.1%}   {:26.1%}".format(tl, band, shortfall))
    print("  (One row is omitted: the bracket whose threshold we cannot")
    print("   establish. Its value is not printed here either - this output is")
    print("   the kind of thing that ends up screenshotted onto a slide.")
    print("   The 1.0 mm row is the WORST case in the table and applies only to")
    print("   panels of 50 cm2 or less.)")
    print()
    # THE CAVEAT TRAVELS WITH ITS ROW, not in a footnote at the bottom. This
    # banner is the fallback demo if the rig fails, which means it gets
    # screenshotted and screenshots get cropped - and the row it belongs to is the
    # last one, where a crop is likeliest to keep the number and lose the note.
    # Keyed on the category rather than written into the loop, so adding a row
    # cannot quietly lose it.
    #
    # Say what is unmeasurable and by whom. "Formed package" is not a legal
    # exemption and must never read as one: the requirement applies, the number
    # below IS the number, and the limitation is OURS. Nor is it true of every pack
    # in this bracket - a perforated or moulded pack can still carry ink-printed
    # characters, which this instrument measures normally - so the caveat is stated
    # as the conditional it actually is.
    _MEASURAND_CAVEAT = {
        CATEGORY_FORMED: (
            "     ^ THE LAW'S NUMBER, NOT A RESULT THIS INSTRUMENT CAN PRODUCE.\n"
            "       If the characters are FORMED IN THE MATERIAL rather than "
            "printed in ink -\n"
            "       blown, moulded, embossed - there is no ink edge to find, and "
            "the measurement\n"
            "       engine refuses with MEASURAND_UNDEFINED before any threshold "
            "is applied.\n"
            "       That refusal is our limit, not an exemption and not the "
            "packer's defence:\n"
            "       the height requirement still applies to the pack. If the same "
            "pack carries\n"
            "       ink-printed characters, they are measured normally."),
    }
    for area, cat in ((40.0, CATEGORY_GENERAL), (75.0, CATEGORY_GENERAL),
                      (300.0, CATEGORY_GENERAL), (75.0, CATEGORY_FORMED)):
        r = _resolve(cat, area)
        print("A = {:7.1f} cm2  {:<40} -> {}".format(
            area, cat,
            "TL = {:.1f} mm".format(r.threshold_mm) if r.resolved
            else "REFUSED " + ", ".join(_codes(r))))
        caveat = _MEASURAND_CAVEAT.get(cat)
        if caveat:
            print(caveat)










