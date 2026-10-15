"""Core logic: weekly cost per tonne-km, the two baselines from the brief, and the flag rule."""
import numpy as np
import pandas as pd

OWN_WINDOW_WEEKS = 8      # brief: trailing 8-week rolling average, strictly before the current week
OWN_SPIKE = 0.10          # flag if cost is >= +10% above the route's own trailing average ...
PEER_GAP = 0.20           # ... or >= +20% above similar routes while also rising vs own history


def load_shipments(path):
    df = pd.read_csv(path, parse_dates=["shipment_date"])
    df["route"] = df["origin"] + "-" + df["destination"]
    # Monday of the week containing shipment_date (weeks run Mon-Sun)
    df["week_of"] = df["shipment_date"] - pd.to_timedelta(df["shipment_date"].dt.weekday, unit="D")
    df["tonne_km"] = df["quantity_tonnes"] * df["distance_km"]
    return df


def weekly_metrics(df):
    """One row per (route, week) with cpt, vs-own-history and vs-similar-routes numbers."""
    wk = (df.groupby(["route", "route_type", "week_of"], as_index=False)
            .agg(cost=("freight_cost_inr", "sum"), tonne_km=("tonne_km", "sum")))
    wk["cpt"] = wk["cost"] / wk["tonne_km"]            # total cost / sum(tonnes x km)

    # --- vs own history: mean of the prior (up to) 8 weekly values, no look-ahead ---
    grid = wk.pivot(index="week_of", columns="route", values="cpt")
    grid = grid.reindex(pd.date_range(grid.index.min(), grid.index.max(), freq="7D"))
    prior = grid.shift(1).rolling(OWN_WINDOW_WEEKS, min_periods=1)
    base = prior.mean().stack().rename("own_base")
    n_prior = prior.count().stack().rename("n_prior_weeks")
    base.index.names = n_prior.index.names = ["week_of", "route"]
    wk = wk.merge(base.reset_index(), on=["week_of", "route"], how="left")
    wk = wk.merge(n_prior.reset_index(), on=["week_of", "route"], how="left")
    wk["vs_own"] = wk["cpt"] / wk["own_base"] - 1

    # --- vs similar routes: same week, same route_type, all OTHER routes ---
    g = wk.groupby(["route_type", "week_of"])["cpt"].agg(["sum", "count"]).rename(
        columns={"sum": "_s", "count": "_k"}).reset_index()
    wk = wk.merge(g, on=["route_type", "week_of"])
    wk["peer_avg"] = np.where(wk["_k"] > 1, (wk["_s"] - wk["cpt"]) / (wk["_k"] - 1).replace(0, np.nan), np.nan)
    wk["vs_peer"] = wk["cpt"] / wk["peer_avg"] - 1
    wk = wk.drop(columns=["_s", "_k"])

    wk["trig_own"] = wk["vs_own"] >= OWN_SPIKE
    wk["trig_peer"] = (wk["vs_own"] > 0) & (wk["vs_peer"] >= PEER_GAP)
    wk["candidate"] = wk["trig_own"] | wk["trig_peer"]
    return wk.sort_values(["week_of", "route"]).reset_index(drop=True)


def pct(x, suffix):
    return "n/a (no prior weeks)" if pd.isna(x) else f"{x * 100:+.1f}% {suffix}"
