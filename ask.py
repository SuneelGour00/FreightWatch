"""Stretch goal: ask plain-English questions about the findings. Answers come ONLY from out/flags.csv.
Examples:  python ask.py "why did Chennai-Bangalore get pricier in March?"
           python ask.py "which routes are unexplained?"
Deterministic keyword/date parsing, no LLM, so it cannot invent a reason."""
import re, sys
import pandas as pd

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]


def answer(q, path="out/flags.csv"):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    ql = q.lower()
    routes = [r for r in df.route.unique() if r.lower() in ql or any(c.lower() in ql for c in r.split("-"))]
    allroutes = pd.read_csv(path.replace("flags.csv", "flags_all_weeks.csv")).route.unique()
    routes = routes or [r for r in allroutes if any(c.lower() in ql for c in r.split("-"))]
    month = next((i for i, m in enumerate(MONTHS, 1) if m in ql or m[:3] + " " in ql + " "), None)
    year = re.search(r"20\d\d", ql)
    sub = df
    if routes: sub = sub[sub.route.isin(routes)]
    if month: sub = sub[sub.week_of.str[5:7].astype(int) == month]
    if year: sub = sub[sub.week_of.str[:4] == year.group()]
    if "unexplained" in ql or "no reason" in ql: sub = sub[sub.flagged == "Yes"]
    if sub.empty:
        return "No flagged cost rises match that question in my results (so I have nothing to explain)."
    lines = [f"{r.route}, week of {r.week_of}: {r.cost_per_tonne_km} per tonne-km, {r.vs_own_history}, "
             f"{r.vs_similar_routes}. Verdict: {r.flagged}"
             + (f" (note {r.matched_note_id})" if r.matched_note_id else "") + f". {r.reason}" for r in sub.itertuples()]
    return "\n".join(lines)


if __name__ == "__main__":
    print(answer(" ".join(sys.argv[1:]) or "which routes are unexplained?"))
