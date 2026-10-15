"""Decides whether a retrieved note genuinely justifies a flagged cost rise.

A note only counts if ALL hold: applies to this route, says costs went UP, its dates cover the week,
and (for fuel-type notes) the size of the rise is compatible with what the note says.
"""
from datetime import timedelta

NOISE_TOLERANCE = 0.05     # weekly cost-per-tonne-km noise is ~4-5%, so allow +5 pts above a note's stated range
BASELINE_WEEKS = 8         # a nationwide step-change stops looking like a "rise" once it is inside the 8-wk baseline


def check_note(note, route, week_of, vs_own, trig_own, trig_peer):
    """Return (ok, why_not). `why_not` is plain English used in the explanation."""
    if not (note.is_global or note.applies_to == route):
        return False, f"it applies to {note.applies_to}, not {route}"
    if note.effect != "increase":
        return False, "it does not describe a cost increase" if note.effect == "no_effect" \
            else "it does not clearly describe a cost increase"
    wk_start, wk_end = week_of.date(), (week_of + timedelta(days=6)).date()
    if wk_end < note.start or (note.end is not None and wk_start > note.end):
        span = f"{note.start} onward" if note.end is None else f"{note.start} to {note.end}"
        return False, f"its dates ({span}) do not cover the week of {wk_start}"
    if note.is_global:   # uniform, nationwide effects (e.g. diesel)
        if trig_peer and not trig_own:
            return False, "a nationwide change raises peers too, so it cannot explain a gap versus similar routes"
        if week_of.date() >= note.start + timedelta(weeks=BASELINE_WEEKS):
            return False, f"its effect is already part of the route's trailing 8-week baseline by {wk_start}"
        if note.max_pct is not None and vs_own > note.max_pct + NOISE_TOLERANCE:
            return False, (f"the note puts the rise at up to {note.max_pct:.0%}, but this week is "
                           f"{vs_own:+.1%} above the route's history")
    return True, ""


def _gap_days(note, week_of):
    wk_start, wk_end = week_of.date(), (week_of + timedelta(days=6)).date()
    if wk_end < note.start:
        return (note.start - wk_end).days
    if note.end is not None and wk_start > note.end:
        return (wk_start - note.end).days
    return 0


def judge(candidates, route, week_of, vs_own, trig_own, trig_peer):
    """candidates: [(Note, similarity)] in retrieval order.
    Returns (matched Note | None, (closest rejected Note, why) | None). The 'closest' note is the rejected
    one whose dates are nearest the week; it is only used to explain why nothing justified the rise."""
    rejected = []
    for note, sim in candidates:
        ok, why = check_note(note, route, week_of, vs_own, trig_own, trig_peer)
        if ok:
            return note, None
        rejected.append((_gap_days(note, week_of), -sim, note.note_id, note, why))
    if not rejected:
        return None, None
    _, _, _, note, why = min(rejected, key=lambda t: t[:3])
    return None, (note, why)
