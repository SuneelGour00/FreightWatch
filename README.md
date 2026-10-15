# Shipping Cost Watcher (FreightTiger case study)

Finds routes whose freight cost per tonne-km is rising in a way that looks out of the ordinary, then checks a set
of context notes to see whether there is a real, documented reason. If no note genuinely supports it, the row says so.

## Run it
```
pip install -r requirements.txt
python run.py                      # writes out/flags.csv  (the deliverable, same columns as sample_output_format)
python eval/run_eval.py            # eval harness (all checks must PASS)
./repro_check.sh                   # 3 runs, byte-for-byte diff
python ask.py "why did Chennai-Bangalore get pricier in March?"   # stretch goal
```

## How it works
1. **Weeks.** `shipment_date` is mapped to the Monday of its Mon-Sun week (`week_of`) before anything else.
2. **Metric.** Per route and week: `cost per tonne-km = sum(freight cost) / sum(tonnes x km)`. Routes are origin-destination;
   `route_type` comes straight from the data.
3. **vs own history.** Mean of the route's weekly values over the trailing 8 weeks, strictly before the current week.
   If fewer than 8 prior weeks exist, all prior weeks are used (no padding). The first week of a route has no
   history, so it shows "n/a" and cannot be flagged on that basis. (This dataset has no missing weeks, so there are
   always 8 prior weeks after week 8.)
4. **vs similar routes.** Same week, mean cost per tonne-km of all *other* routes with the same `route_type`.
5. **Flag rule (my choice, the brief leaves it open).** A route-week is a candidate if either
   - it is >= +10% above its own trailing average (weekly noise is ~4-5%, so 10% is about two sigmas), or
   - it is rising (> 0% vs own history) and >= +20% above similar routes.
   The second rule exists because Mumbai-Pune creeps up slowly (only 3-9% a week vs its own average) while drifting
   far above Delhi-Jaipur. Mumbai-Pune is structurally ~10% above Delhi-Jaipur even in normal times, hence 20% not 10%.
   Only candidates appear in the output file (as in the brief's sample); the full 728-row weekly table is in
   `out/flags_all_weeks.csv` for audit.
6. **Notes (RAG, no LLM).** Each note is parsed into: effect (cost increase / no effect), route scope, date window
   (explicit "Feb 24 to Mar 8", "starting this week", or the note's own week) and any stated % range.
   Notes are embedded as TF-IDF vectors; for a flagged route I pre-filter to notes that cover that route or
   "All Routes", then rank by cosine similarity.
7. **Verifier.** A note justifies a row only if ALL hold: applies to this route; says costs went UP; its dates overlap
   the week; and, for nationwide notes (diesel), it can explain a rise vs *own history* but not a gap vs *peers*
   (peers got the same diesel increase), the rise is within the stated range + 5 pts of noise, and the effect is not
   already inside the 8-week baseline. Anything else is `Yes` (unexplained) with a blank `matched_note_id`.
8. **Explanations are templated from the note's own sentence**, so a justified reason can only say what the note says.

## Results
728 route-weeks, 20 flagged: 4 justified (N001 x2, N002, N003), 16 unexplained. Includes Delhi-Jaipur Nov 2024
(unexplained), Chennai-Bangalore flood weeks (justified up to the note's end date, Mar 8; the two later weeks stay
unexplained because the note's window ended), and a 12-week Mumbai-Pune creep in H2 2025 that nothing explains.

## How I convinced myself it is right (`eval/run_eval.py`, 33 checks, all pass)
- **Numbers:** the brief's sample file contains three rows with cost, both percentages and verdicts. All three are
  reproduced exactly, which independently validates weekly grouping, both baselines and the peer maths.
- **Labelled set** (`eval/labeled_cases.csv`): 10 route-weeks with expected verdict + note, read directly from the notes
  (e.g. Mar 10 is outside the flood window, so it must NOT be justified). Honest caveat: the first 8 labels were set from
  the notes before tuning; the last two (Mumbai-Pune Dec, Mumbai-Delhi May) I added after seeing the output, so they
  document behaviour rather than test it. The Mumbai-Delhi May 12 call is the most borderline in the file (+11.6% vs a stated
  5-7% diesel rise, accepted only because of the +5 pt noise allowance).
- **Adversarial tests:** wrong route, wrong window, "costs not affected" note, nationwide note vs a 30% spike,
  nationwide note vs peer-only gap, stale diesel note - all rejected.
- **Hallucination guard:** every justified row must cite an existing note id and quote that note's sentence.
- **Quiet weeks** are checked to confirm they are not flagged.

## Reproducibility
`./repro_check.sh` runs the pipeline three times and diffs the CSV, the weekly table and the log. Result in
`out/repro_check_result.txt`: identical (same SHA-256). Nothing is random: no LLM, deterministic tie-breaks in retrieval.

## Cost of running it
LLM calls: 0. Input tokens: 0. Output tokens: 0. Cost: $0 (TF-IDF runs locally in well under a second). See `TOKEN_COST_LOG.md`.

## Limitations / trade-offs
- TF-IDF is not a neural embedding model. With 10 short notes it retrieves correctly, and it is deterministic and free,
  but it would not understand paraphrases at scale. The route/date/effect verification is what actually protects against
  wrong citations, not the similarity score. Swapping in a sentence-embedding model + vector DB only changes
  `NoteRetriever`.
- Note parsing uses regex patterns written for this note style; unusual wording would fall to "unclear" and become
  unexplained (the safe direction).
- Thresholds (10% / 20% / 5 pts) are judgment calls; they are constants at the top of `metrics.py` and `verify.py`.

## Layout
```
run.py  ask.py  repro_check.sh  requirements.txt
freight_watch/  metrics.py (maths + flag rule)  notes.py (parse + retrieve)  verify.py (justification rules)  pipeline.py
eval/           run_eval.py  labeled_cases.csv
data/           inputs      out/  flags.csv (deliverable)  flags_all_weeks.csv  flags_run_log.json  run1-3/
```
