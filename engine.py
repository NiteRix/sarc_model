"""Sarcoidosis likelihood score.

How it works
1. Each symptom / finding gets points (-2 to 5). It starts from clinical
   knowledge of how typical it is for sarcoidosis, then is adjusted by the
   case sheet: the more often it appears in sarcoidosis cases compared with
   the other diseases, the more points it gets. Findings more typical of the
   look-alike diseases (TB, lymphoma) get negative points.
2. Each lab gets points by how far it is outside its normal range (severity).
3. Points are added up and turned into a percentage: the patient starts at a
   base chance (pretest probability, default 10%) and every 2 points doubles
   the odds (points are on a log2 likelihood-ratio scale).
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUTCOME = "Sarcoidosis?"


def load_cases(path=ROOT / "data" / "cases.xlsx"):
    df = pd.read_excel(path, sheet_name="Clean cases", header=1)
    df = df[df["Case #"].notna()].copy()
    df = df[df[OUTCOME].isin(["Yes", "No"])]
    df = df[~df["Case #"].isin(CONFIG["exclude_cases"])]
    df["y"] = (df[OUTCOME] == "Yes").astype(int)
    return df.reset_index(drop=True)


def learn_points(df):
    rows = []
    sar, oth = df[df.y == 1], df[df.y == 0]
    for f in CONFIG["features"]:
        ys, cs = (sar[f] == "Yes").sum(), (sar[f].isin(["Yes", "No"])).sum()
        yo, co = (oth[f] == "Yes").sum(), (oth[f].isin(["Yes", "No"])).sum()
        p_s = (ys + 1) / (cs + 2)
        p_o = (yo + 1) / (co + 2)
        ratio = p_s / p_o
        n = cs + co
        k = CONFIG["prior_weight"]
        prior = CONFIG["prior_points"].get(f, 0)
        blended = (k * prior + n * 2 * math.log2(ratio)) / (k + n)
        pts = int(np.clip(round(blended), CONFIG["min_points"], CONFIG["max_points"]))
        rows.append({
            "Finding": f,
            "Sarcoidosis cases with it": int(ys), "Sarcoidosis cases checked": int(cs),
            "% in sarcoidosis": ys / cs if cs else None,
            "Other cases with it": int(yo), "Other cases checked": int(co),
            "% in other diseases": yo / co if co else None,
            "Times more common in sarcoidosis": round(ratio, 2),
            "Starting points (clinical knowledge)": prior,
            "Points": pts,
        })
    return pd.DataFrame(rows).sort_values(["Points", "% in sarcoidosis"], ascending=False).reset_index(drop=True)


def lab_points(name, value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0, None
    lab = CONFIG["labs"][name]
    if lab["direction"] == "high":
        ratio = value / lab["high"] if lab["high"] else 0
    else:
        ratio = lab["low"] / value if value > 0 else 999
    frac = 0.0
    for limit, f in CONFIG["severity_tiers"]:
        if ratio <= limit:
            frac = f
            break
    pts = int(round(lab["max_points"] * frac))
    status = "Normal" if ratio <= 1 else ("High" if lab["direction"] == "high" else "Low")
    return pts, (status, round(ratio, 2))


def score(patient, points_table):
    """patient: {"symptoms": {finding: "Yes"/"No"/...}, "labs": {lab: value}}"""
    pts = dict(zip(points_table["Finding"], points_table["Points"]))
    breakdown = []
    for f, v in patient.get("symptoms", {}).items():
        if v == "Yes" and pts.get(f, 0) != 0:
            breakdown.append((f, pts[f]))
    for name, v in patient.get("labs", {}).items():
        p, info = lab_points(name, v)
        if p > 0:
            breakdown.append((f"{name} {v} ({info[0]}, {info[1]}x limit)", p))
    breakdown.sort(key=lambda x: -x[1])
    return sum(p for _, p in breakdown), breakdown


def row_to_patient(row):
    sym = {f: row.get(f) for f in CONFIG["features"]}
    labs = {}
    for name, lab in CONFIG["labs"].items():
        col = lab.get("column")
        if col and col in row and pd.notna(row[col]):
            labs[name] = float(row[col])
    return {"symptoms": sym, "labs": labs}


def probability(pretest, total):
    """Every 2 points doubles the odds, starting from the pretest probability."""
    odds = pretest / (1 - pretest) * 2 ** (total / 2)
    return min(odds / (1 + odds), 0.99)


def train(df=None):
    df = load_cases() if df is None else df
    table = learn_points(df)
    scores = [score(row_to_patient(r), table)[0] for _, r in df.iterrows()]
    return table, CONFIG["pretest_probability"], scores


def leave_one_out(df):
    """Honest test: each case is scored by a model that never saw it."""
    out = []
    for i in range(len(df)):
        tr = df.drop(index=i).reset_index(drop=True)
        table, model, _ = train(tr)
        r = df.iloc[i]
        total, _ = score(row_to_patient(r), table)
        out.append({"Case #": int(r["Case #"]), "Final diagnosis": r["Final diagnosis"],
                    "Actual": "Sarcoidosis" if r.y else "Other",
                    "Score": total, "Probability": probability(model, total)})
    res = pd.DataFrame(out)
    res["Predicted"] = np.where(res.Probability >= 0.25, "Sarcoidosis", "Other")
    res["Correct"] = res.Predicted == res.Actual
    return res
