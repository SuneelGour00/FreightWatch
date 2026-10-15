"""End-to-end: shipments + notes -> output rows (one per flagged route-week)."""
import pandas as pd
from .metrics import load_shipments, weekly_metrics, pct
from .notes import load_notes, NoteRetriever
from .verify import judge

COLUMNS = ["route", "week_of", "cost_per_tonne_km", "vs_own_history", "vs_similar_routes",
           "flagged", "matched_note_id", "reason"]


def first_sentence(text):
    return text.split(". ")[0].rstrip(".") + "."


def explain(note, closest):
    if note is not None:
        return (f"Matches note {note.note_id} dated {note.date}: {first_sentence(note.text)} "
                f"The cost rise has a clear explanation.")
    if closest is not None:
        n, why = closest
        return (f"The closest note ({n.note_id}, {n.date}) does not support a justification: {why}. "
                f"No genuine justification found; flagged for review.")
    return "No matching note found for this route or date range. Cost rise looks unexplained and worth a human review."


def build_output(shipments_csv, notes_csv):
    metrics = weekly_metrics(load_shipments(shipments_csv))
    retriever = NoteRetriever(load_notes(notes_csv))
    rows = []
    for r in metrics[metrics["candidate"]].itertuples():
        note, closest = judge(retriever.search(r.route), r.route, r.week_of, r.vs_own, r.trig_own, r.trig_peer)
        rows.append({
            "route": r.route,
            "week_of": r.week_of.strftime("%Y-%m-%d"),
            "cost_per_tonne_km": f"{r.cpt:.2f}",
            "vs_own_history": pct(r.vs_own, "vs this route's past average"),
            "vs_similar_routes": pct(r.vs_peer, "vs similar-length routes this week"),
            "flagged": "No (justified)" if note else "Yes",
            "matched_note_id": note.note_id if note else "",
            "reason": explain(note, closest),
        })
    return pd.DataFrame(rows, columns=COLUMNS), metrics
