"""Context notes: structured annotation + deterministic vector retrieval (TF-IDF, cosine).

No LLM is involved, so there is no randomness, no token spend and nothing that can invent a reason.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

NO_EFFECT = re.compile(
    r"not (?:significantly )?affected|not part of this dataset|no (?:major|significant) disruptions|"
    r"remained (?:stable|normal)|without a rate change|returned to normal|improved road conditions", re.I)
INCREASE = re.compile(r"higher (?:trip )?costs|surcharge|pushing up|prices rose|price increase|rose", re.I)
RANGE_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%")
EXPLICIT_WINDOW = re.compile(r"from ([A-Z][a-z]{2}) (\d{1,2}) to ([A-Z][a-z]{2}) (\d{1,2})")
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


@dataclass(frozen=True)
class Note:
    note_id: str
    date: date
    applies_to: str
    text: str
    effect: str            # "increase" | "no_effect" | "unclear"
    start: date
    end: date | None       # None = open-ended ("starting this week")
    max_pct: float | None  # upper end of a stated % range, if any

    @property
    def is_global(self):
        return self.applies_to.strip().lower() == "all routes"


def _effect(text):
    if NO_EFFECT.search(text):
        return "no_effect"          # checked first: "toll plaza ... not part of this dataset"
    return "increase" if INCREASE.search(text) else "unclear"


def _window(d, text):
    m = EXPLICIT_WINDOW.search(text)
    if m:
        a, b = MONTHS[m.group(1)], MONTHS[m.group(3)]
        return date(d.year, a, int(m.group(2))), date(d.year, b, int(m.group(4)))
    if re.search(r"\bstarting\b", text, re.I):
        return d, None
    return d, d + timedelta(days=6)   # otherwise the note speaks about its own week


def load_notes(path):
    out = []
    for r in pd.read_csv(path).itertuples():
        d = pd.Timestamp(r.date).date()
        s, e = _window(d, r.note)
        pct = RANGE_PCT.search(r.note)
        out.append(Note(r.note_id, d, r.applies_to, r.note, _effect(r.note), s, e,
                        float(pct.group(2)) / 100 if pct else None))
    return sorted(out, key=lambda n: n.note_id)


class NoteRetriever:
    """Embeds notes (TF-IDF vectors) and returns the top-k by cosine similarity to a route query."""

    def __init__(self, notes):
        self.notes = notes
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform([f"{n.applies_to}. {n.text}" for n in notes])

    def search(self, route, k=5):
        """Metadata pre-filter (note must cover this route or 'All Routes'), then rank by cosine similarity."""
        q = self.vec.transform([f"{route.replace('-', ' ')} freight cost increase surcharge disruption "
                                f"diesel fuel toll flooding festival weather"])
        sims = (self.matrix @ q.T).toarray().ravel()
        idx = [i for i, n in enumerate(self.notes) if n.is_global or n.applies_to == route]
        idx.sort(key=lambda i: (-round(sims[i], 10), self.notes[i].note_id))   # deterministic tie-break
        return [(self.notes[i], float(sims[i])) for i in idx[:k]]
