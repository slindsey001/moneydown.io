"""Power rankings.

Ranks all 32 teams by season-to-date net EPA per play (offense EPA per play
minus defense EPA per play allowed). No opponent adjustments, no vibes.

    python rankings.py --week 7          # writes out/week_07/00_power_rankings.png
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb

from charts import ACCENT, BRAND, DPI, FONT, GRID, INK, INK_2, INK_3, SURFACE, load, scrimmage

GOOD = "#3987e5"   # diverging pole: better than league average
BAD = "#e66767"    # diverging pole: worse than league average


def records(df, week):
    g = df[df.week <= week].groupby("game_id").agg(
        home=("home_team", "first"), away=("away_team", "first"),
        hs=("total_home_score", "last"), as_=("total_away_score", "last"), desc=("desc", "last"))
    g = g[g.desc == "END GAME"]
    rec = {}
    for r in g.itertuples():
        for team, us, them in [(r.home, r.hs, r.as_), (r.away, r.as_, r.hs)]:
            w, l, t = rec.get(team, (0, 0, 0))
            rec[team] = (w + (us > them), l + (us < them), t + (us == them))
    return rec


def ats(df, week):
    """Record against the closing spread. spread_line > 0 means the home team was favored."""
    g = df[df.week <= week].groupby("game_id").agg(
        home=("home_team", "first"), away=("away_team", "first"), spread=("spread_line", "first"),
        result=("result", "first"), desc=("desc", "last"))
    g = g[(g.desc == "END GAME") & g.spread.notna() & g.result.notna()]
    rec = {}
    for r in g.itertuples():
        m = r.result - r.spread           # > 0: home covered
        for team, edge in [(r.home, m), (r.away, -m)]:
            w, l, p = rec.get(team, (0, 0, 0))
            rec[team] = (w + (edge > 0), l + (edge < 0), p + (edge == 0))
    return rec


def table(df, week):
    """Season-to-date ranking through `week`, one dict per team, best first."""
    s = scrimmage(df[df.week <= week])
    off = s.groupby("posteam").epa.mean()
    dfn = s.groupby("defteam").epa.mean()
    pas = s[s.play_type == "pass"].groupby("posteam").epa.mean()
    rus = s[s.play_type == "run"].groupby("posteam").epa.mean()
    succ = s.groupby("posteam").success.mean()
    recent = s[s.week > week - 3]
    last3 = recent.groupby("posteam").epa.mean() - recent.groupby("defteam").epa.mean()
    t = pd.DataFrame({"off": off, "def": dfn, "pass": pas, "rush": rus, "succ": succ, "last3": last3})
    t["net"] = t.off - t["def"]
    t = t.sort_values("net", ascending=False)
    t["rank"] = np.arange(1, len(t) + 1)

    prev = None
    if week > 1:
        sp = scrimmage(df[df.week <= week - 1])
        pn = (sp.groupby("posteam").epa.mean() - sp.groupby("defteam").epa.mean()).sort_values(ascending=False)
        prev = {team: i + 1 for i, team in enumerate(pn.index)}

    # heat: each column as a z-score, sign flipped where lower is better
    def z(col, flip=False):
        v = t[col]
        out = (v - v.mean()) / v.std()
        return (-out if flip else out).clip(-2.5, 2.5)

    heat = {c: z(c, flip=(c == "def")) for c in ["net", "off", "def", "pass", "rush", "succ", "last3"]}
    ranks = {c: t[c].rank(ascending=(c == "def"), method="min").astype(int) for c in ["off", "def"]}
    rec = records(df, week)
    cover = ats(df, week)
    rows = []
    for team, r in t.iterrows():
        w, l, ti = rec.get(team, (0, 0, 0))
        rows.append({
            "rank": int(r["rank"]), "team": team,
            "move": (prev[team] - int(r["rank"])) if prev and team in prev else 0,
            "record": f"{w}-{l}" + (f"-{ti}" if ti else ""),
            "ats": "-".join(map(str, cover.get(team, (0, 0, 0))[:2])) + (
                f"-{cover[team][2]}" if cover.get(team, (0, 0, 0))[2] else ""),
            "net": round(r.net, 3), "off": round(r.off, 3), "def": round(r["def"], 3),
            "pass": round(r["pass"], 3), "rush": round(r.rush, 3), "succ": round(r.succ * 100, 1),
            "last3": round(r.last3, 3),
            "off_rank": int(ranks["off"][team]), "def_rank": int(ranks["def"][team]),
            "heat": {c: round(float(heat[c][team]), 2) for c in heat},
        })
    return rows


def fmt(v):
    v = round(v, 2) + 0.0
    return "0.00" if v == 0 else f"{v:+.2f}"


def heat_rgb(z):
    """Blend a diverging pole into the surface by |z|; z=0 stays the surface."""
    a = min(abs(z) / 2.5, 1) * 0.62
    pole = np.array(to_rgb(GOOD if z > 0 else BAD))
    base = np.array(to_rgb(SURFACE))
    return tuple(base * (1 - a) + pole * a)


def png(rows, week, season, out_dir):
    """Social-size image (1080 x 1350) of the full 32-team table."""
    fig = plt.figure(figsize=(7.2, 9.0), dpi=DPI)
    fig.text(0.06, 0.955, BRAND, fontsize=11, fontweight="bold", color=ACCENT, family=FONT)
    fig.text(0.94, 0.955, f"THROUGH WEEK {week}  ·  {season}", fontsize=10, color=INK_2, ha="right", family=FONT)
    fig.text(0.06, 0.905, "Power rankings", fontsize=21, fontweight="bold", color=INK, family=FONT)
    fig.text(0.06, 0.872, "Ranked by net EPA per play. ATS = record against the closing spread.",
             fontsize=10, color=INK_2, family=FONT)
    fig.text(0.06, 0.025, "Data: nflverse play-by-play  ·  Net = offense EPA/play minus defense EPA/play allowed",
             fontsize=8, color=INK_3, family=FONT)

    cols = [("#", 0.06, "left"), ("", 0.105, "center"), ("TEAM", 0.14, "left"), ("REC", 0.215, "left"),
            ("ATS", 0.295, "left"), ("NET", 0.435, "center"), ("OFF", 0.545, "center"), ("DEF", 0.655, "center"),
            ("PASS", 0.765, "center"), ("RUSH", 0.875, "center")]
    top, bottom = 0.835, 0.055
    h = (top - bottom) / (len(rows) + 1)
    y = top - h / 2
    for name, x, ha in cols:
        fig.text(x, y, name, fontsize=7.5, color=INK_3, ha=ha, va="center", family=FONT, fontweight="bold")
    cw = 0.10
    for r in rows:
        y -= h
        fig.text(0.06, y, str(r["rank"]), fontsize=9, color=INK, va="center", family=FONT, fontweight="bold")
        mv = r["move"]
        if mv:
            fig.text(0.105, y, f"{'▲' if mv > 0 else '▼'}{abs(mv)}", fontsize=6.5, va="center", ha="center",
                     color=INK_2, family="DejaVu Sans")
        fig.text(0.14, y, r["team"], fontsize=9.5, color=INK, va="center", family=FONT, fontweight="bold")
        fig.text(0.215, y, r["record"], fontsize=8.5, color=INK_2, va="center", family=FONT)
        fig.text(0.295, y, r["ats"], fontsize=8.5, color=INK_2, va="center", family=FONT)
        for key, (_, x, _) in zip(["net", "off", "def", "pass", "rush"], cols[5:]):
            fig.patches.append(plt.Rectangle((x - cw / 2, y - h * 0.44), cw, h * 0.88, transform=fig.transFigure,
                                             facecolor=heat_rgb(r["heat"][key]), edgecolor="none"))
            fig.text(x, y, fmt(r[key]), fontsize=8.5, color=INK, ha="center", va="center", family=FONT)
    path = os.path.join(out_dir, "00_power_rankings.png")
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    print("saved", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--data")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    df = load(a.season, a.data)
    out = os.path.join(a.out, f"week_{a.week:02d}")
    os.makedirs(out, exist_ok=True)
    png(table(df, a.week), a.week, a.season, out)


if __name__ == "__main__":
    main()
