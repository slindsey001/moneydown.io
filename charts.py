"""Weekly charts.

Builds a branded set of NFL charts for one week from nflverse play-by-play data.

Usage:
    python charts.py --week 5
    python charts.py --week 5 --season 2026 --data path/to/pbp.csv.gz --out out

If --data is omitted, the season's play-by-play CSV is downloaded from nflverse.
Each chart is saved as a 1080x1350 PNG (4:5, sized for social carousels).
"""

import argparse
import json
import os
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

# ---------------------------------------------------------------- brand
SURFACE = "#1a1a19"
INK = "#f0efec"        # primary text
INK_2 = "#c3c2b7"      # secondary text
INK_3 = "#8a897f"      # muted text / quadrant notes
GRID = "#383835"
ACCENT = "#3987e5"     # categorical slot 1 (blue)
ACCENT_2 = "#d95926"   # slot 2 (orange)
ACCENT_3 = "#199e70"   # slot 3 (aqua)
NEUTRAL = "#5c5b55"    # de-emphasized marks
_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "brand.json")) as _fh:
    BRAND_INFO = json.load(_fh)
BRAND = BRAND_INFO["name"].upper()
W_IN, H_IN, DPI = 7.2, 9.0, 150   # 1080 x 1350 px

FONT = "Inter" if any("Inter" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
plt.rcParams.update({
    "font.family": FONT,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_3,
    "ytick.color": INK_3,
    "axes.edgecolor": GRID,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})


def frame(title, subtitle, week, season, note=""):
    """A figure with the brand header and footer; returns (fig, ax)."""
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
    fig.text(0.06, 0.955, BRAND, fontsize=11, fontweight="bold", color=ACCENT)
    fig.text(0.94, 0.955, f"WEEK {week}  ·  {season}", fontsize=10, color=INK_2, ha="right")
    fig.text(0.06, 0.905, title, fontsize=21, fontweight="bold", color=INK)
    fig.text(0.06, 0.872, subtitle, fontsize=11, color=INK_2)
    foot = "Data: nflverse play-by-play"
    if note:
        foot += f"  ·  {note}"
    fig.text(0.06, 0.03, foot, fontsize=8.5, color=INK_3)
    ax = fig.add_axes([0.11, 0.10, 0.83, 0.73])
    return fig, ax


def save(fig, out_dir, name):
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print("saved", path)


# ---------------------------------------------------------------- data
def load(season, data_path):
    if not data_path:
        os.makedirs("data", exist_ok=True)
        data_path = f"data/pbp_{season}.csv.gz"
        if not os.path.exists(data_path):
            url = ("https://github.com/nflverse/nflverse-data/releases/download/pbp/"
                   f"play_by_play_{season}.csv.gz")
            print("downloading", url)
            urllib.request.urlretrieve(url, data_path)
    df = pd.read_csv(data_path, low_memory=False)
    return df[df.season_type == "REG"]


def scrimmage(df):
    return df[df.play_type.isin(["pass", "run"]) & df.epa.notna()]


def clock(row):
    s = row.quarter_seconds_remaining
    q = "OT" if row.qtr >= 5 else f"Q{int(row.qtr)}"
    return f"{q} {int(s // 60)}:{int(s % 60):02d}"


def short_desc(row):
    yds = int(row.yards_gained) if pd.notna(row.yards_gained) else 0
    if row.get("interception") == 1:
        return f"{row.passer_player_name} intercepted"
    if row.get("fumble_lost") == 1:
        who = row.get("fumbled_1_player_name")
        return f"{who} fumble lost" if pd.notna(who) else "Fumble lost"
    td = " TD" if row.touchdown == 1 else ""
    gain = "no gain" if yds == 0 else f"{yds} yds"
    if row.sack == 1:
        return f"{row.passer_player_name} sacked"
    if row.play_type == "pass":
        if row.get("complete_pass") == 0:
            to = f" for {row.receiver_player_name}" if pd.notna(row.receiver_player_name) else ""
            return f"{row.passer_player_name} incomplete{to}"
        if pd.notna(row.receiver_player_name):
            return f"{row.passer_player_name} to {row.receiver_player_name}, {gain}{td}"
    if row.play_type == "run" and pd.notna(row.rusher_player_name):
        return f"{row.rusher_player_name} run, {gain}{td}"
    if row.play_type == "field_goal":
        res = {"made": "good", "missed": "no good", "blocked": "blocked"}.get(row.field_goal_result, row.field_goal_result)
        who = f"{row.kicker_player_name} " if pd.notna(row.get("kicker_player_name")) else ""
        return f"{who}{int(row.kick_distance)}-yd FG {res}" if pd.notna(row.kick_distance) else "Field goal"
    if row.play_type == "extra_point":
        res = {"good": "good", "failed": "no good", "blocked": "blocked"}.get(row.get("extra_point_result"), "")
        who = f"{row.kicker_player_name} " if pd.notna(row.get("kicker_player_name")) else ""
        return f"{who}extra point {res}".strip()
    if row.play_type == "kickoff" and pd.notna(row.get("kickoff_returner_player_name")):
        ry = int(row.return_yards) if pd.notna(row.return_yards) else 0
        return f"{row.kickoff_returner_player_name} {ry}-yd kick return{td}"
    if row.play_type == "punt" and pd.notna(row.get("punt_returner_player_name")):
        ry = int(row.return_yards) if pd.notna(row.return_yards) else 0
        return f"{row.punt_returner_player_name} punt return, " + ("no gain" if ry == 0 else f"{ry} yds") + td
    return str(row.play_type).replace("_", " ").capitalize()


def label_points(ax, xs, ys, labels, color=INK, size=8.5):
    """Label every point without collisions, measured in pixels.

    Tries spots around each point (right, left, above, below, then farther out);
    a label pushed away from its dot gets a thin leader line.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axbox = ax.get_window_extent(renderer)
    pts = [ax.transData.transform((x, y)) for x, y in zip(xs, ys)]
    r = 7  # dot radius in px, plus a little air
    obstacles = [(px - r, py - r, px + r, py + r) for px, py in pts]
    placed = []

    def overlap(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    cands = []
    for dist in (9, 22, 38, 56):
        cands += [(dist, 0, "left", "center"), (-dist, 0, "right", "center"),
                  (0, dist, "center", "bottom"), (0, -dist, "center", "top"),
                  (dist, dist * .8, "left", "bottom"), (dist, -dist * .8, "left", "top"),
                  (-dist, dist * .8, "right", "bottom"), (-dist, -dist * .8, "right", "top")]

    order = sorted(range(len(pts)), key=lambda i: -sum(  # crowded points choose first
        1 for j in range(len(pts)) if abs(pts[i][0] - pts[j][0]) < 120 and abs(pts[i][1] - pts[j][1]) < 40))
    for i in order:
        x, y, t = xs.iloc[i] if hasattr(xs, "iloc") else xs[i], ys.iloc[i] if hasattr(ys, "iloc") else ys[i], list(labels)[i]
        best, best_score = None, None
        for dx, dy, ha, va in cands:
            txt = ax.annotate(t, (x, y), xytext=(dx, dy), textcoords="offset pixels",
                              ha=ha, va=va, fontsize=size, color=color)
            bb = txt.get_window_extent(renderer).expanded(1.04, 1.15)
            box = (bb.x0, bb.y0, bb.x1, bb.y1)
            txt.remove()
            inside = box[0] >= axbox.x0 and box[2] <= axbox.x1 and box[1] >= axbox.y0 and box[3] <= axbox.y1
            hits = sum(overlap(box, o) for k, o in enumerate(obstacles) if k != i) + sum(overlap(box, p) for p in placed)
            score = hits * 10 + (0 if inside else 50) + abs(dx) / 100
            if best_score is None or score < best_score:
                best, best_score = (dx, dy, ha, va, box), score
            if hits == 0 and inside:
                break
        dx, dy, ha, va, box = best
        far = abs(dx) > 9 or abs(dy) > 9
        ax.annotate(t, (x, y), xytext=(dx, dy), textcoords="offset pixels", ha=ha, va=va,
                    fontsize=size, color=color, zorder=5,
                    arrowprops=dict(arrowstyle="-", color=INK_3, lw=0.7, shrinkA=0, shrinkB=5) if far else None)
        placed.append(box)


# ---------------------------------------------------------------- charts
def qb_scatter(df, week, season, out):
    w = df[(df.week == week) & (df.qb_dropback == 1) & df.epa.notna()]
    q = (w.groupby(["passer_player_name", "posteam"])
           .agg(n=("epa", "size"), epa=("epa", "mean"), cpoe=("cpoe", "mean"))
           .reset_index())
    q = q[q.n >= 20]
    fig, ax = frame("Who actually played well?", "QB efficiency vs accuracy, min. 20 dropbacks",
                    week, season, "EPA = expected points added; CPOE = completion % over expected")
    ax.axhline(q.epa.mean(), color=INK_3, lw=1, ls="--", zorder=1)
    ax.axvline(q.cpoe.mean(), color=INK_3, lw=1, ls="--", zorder=1)
    ax.scatter(q.cpoe, q.epa, s=70, color=ACCENT, edgecolor=SURFACE, linewidth=2, zorder=3)
    pad_x = (q.cpoe.max() - q.cpoe.min()) * 0.12
    pad_y = (q.epa.max() - q.epa.min()) * 0.08
    ax.set_xlim(q.cpoe.min() - pad_x, q.cpoe.max() + pad_x * 1.6)
    ax.set_ylim(q.epa.min() - pad_y, q.epa.max() + pad_y)
    label_points(ax, q.cpoe, q.epa, [f"{n} {t}" for n, t in zip(q.passer_player_name, q.posteam)])
    kw = dict(fontsize=9, color=INK_3, transform=ax.transAxes, fontstyle="italic")
    ax.text(0.98, 0.98, "Accurate & efficient", ha="right", va="top", **kw)
    ax.text(0.02, 0.02, "Rough day", ha="left", va="bottom", **kw)
    ax.set_xlabel("CPOE (completion % over expected)")
    ax.set_ylabel("EPA per dropback")
    save(fig, out, "01_qb_efficiency.png")


def team_tiers(df, week, season, out):
    w = scrimmage(df[df.week == week])
    off = w.groupby("posteam").epa.mean()
    dfn = w.groupby("defteam").epa.mean()
    t = pd.DataFrame({"off": off, "def": dfn}).dropna()
    fig, ax = frame("Team tiers", "Offense vs defense, EPA per play  ·  up and right is better",
                    week, season, "Defense axis flipped: higher = fewer points allowed")
    ax.axhline(t["def"].mean(), color=INK_3, lw=1, ls="--", zorder=1)
    ax.axvline(t.off.mean(), color=INK_3, lw=1, ls="--", zorder=1)
    ax.scatter(t.off, t["def"], s=70, color=ACCENT, edgecolor=SURFACE, linewidth=2, zorder=3)
    px = (t.off.max() - t.off.min()) * 0.1
    py = (t["def"].max() - t["def"].min()) * 0.08
    ax.set_xlim(t.off.min() - px, t.off.max() + px)
    ax.set_ylim(t["def"].max() + py, t["def"].min() - py)   # inverted
    label_points(ax, t.off, t["def"], t.index, size=9)
    kw = dict(fontsize=9, color=INK_3, transform=ax.transAxes, fontstyle="italic")
    ax.text(0.98, 0.98, "Good at everything", ha="right", va="top", **kw)
    ax.text(0.02, 0.98, "Defense carried", ha="left", va="top", **kw)
    ax.text(0.98, 0.02, "Shootout specialists", ha="right", va="bottom", **kw)
    ax.text(0.02, 0.02, "Bad week", ha="left", va="bottom", **kw)
    ax.set_xlabel("Offense EPA per play")
    ax.set_ylabel("Defense EPA per play allowed")
    save(fig, out, "02_team_tiers.png")


def game_of_week(df, week, season, out):
    w = df[(df.week == week) & df.home_wp.notna()].copy()
    swing = w.groupby("game_id").wpa.apply(lambda s: s.abs().sum())
    gid = swing.idxmax()
    real = ["pass", "run", "field_goal", "punt", "kickoff", "extra_point", "qb_kneel", "qb_spike"]
    g = w[(w.game_id == gid) & w.play_type.isin(real)].copy()
    g["t"] = (3600 - g.game_seconds_remaining).where(g.qtr <= 4, 3600 + 600 - g.quarter_seconds_remaining)
    g = g.sort_values("play_id")
    home, away = g.home_team.iloc[0], g.away_team.iloc[0]
    last = df[df.game_id == gid].iloc[-1]
    hs, as_ = int(last.total_home_score), int(last.total_away_score)
    # finish the line at the final result
    end_t = max(g.t.max(), 3600)
    g = pd.concat([g, pd.DataFrame({"t": [end_t], "home_wp": [1.0 if hs > as_ else 0.0 if hs < as_ else 0.5]})])
    ot = " (OT)" if g.qtr.max() >= 5 else ""
    winner = f"{home} {hs}, {away} {as_}" if hs >= as_ else f"{away} {as_}, {home} {hs}"
    fig, ax = frame("Game of the week", f"{away} at {home}  ·  Final: {winner}{ot}", week, season,
                    "Picked by total win-probability swing")
    x, y = g.t / 60, g.home_wp * 100
    ax.fill_between(x, 50, y, where=y >= 50, color=ACCENT, alpha=0.25, lw=0, interpolate=True)
    ax.fill_between(x, 50, y, where=y < 50, color=ACCENT_2, alpha=0.25, lw=0, interpolate=True)
    ax.plot(x, y, color=INK, lw=2)
    end = x.max()
    ax.set_xlim(0, end)
    ax.set_ylim(0, 100)
    ax.axhline(50, color=INK_3, lw=1)
    for q in [15, 30, 45, 60]:
        if q < end:
            ax.axvline(q, color=GRID, lw=1)
    ticks = [7.5, 22.5, 37.5, 52.5] + ([65] if end > 60 else [])
    ax.set_xticks(ticks)
    ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4", "OT"][:len(ticks)])
    ax.grid(axis="x", visible=False)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels([f"{away} 100%", "75%", "50%", "75%", f"{home} 100%"])
    # annotate the two biggest swings
    top = g.reindex(g.wpa.abs().sort_values(ascending=False).index).head(2)
    for k, (_, r) in enumerate(top.iterrows()):
        xx, yy = r.t / 60, r.home_wp * 100 + r.wpa * 100 * (1 if r.posteam == home else -1)
        yy = min(max(yy, 6), 94)
        txt = f"{r.posteam}  ·  {clock(r)}\n{short_desc(r)}"
        frac = xx / end
        ha = "right" if frac > 0.7 else "left" if frac < 0.3 else "center"
        ax.annotate(txt, (xx, yy), xytext=(-8 if ha == "right" else 8 if ha == "left" else 0,
                                           (40 + 55 * k) if yy < 50 else -(48 + 55 * k)), textcoords="offset points",
                    ha=ha, va="center", fontsize=8.5, color=INK, arrowprops=dict(arrowstyle="-", color=INK_3, lw=1),
                    bbox=dict(boxstyle="round,pad=0.3", fc=SURFACE, ec=GRID))
    save(fig, out, "03_game_of_the_week.png")


def swing_plays(df, week, season, out):
    w = df[(df.week == week) & df.wpa.notna() & df.posteam.notna()].copy()
    w["swing"] = w.wpa.abs() * 100
    top = w.sort_values("swing", ascending=False).head(8).iloc[::-1]
    fig, ax = frame("Biggest swing plays", "Change in win probability on a single play", week, season)
    ax.set_position([0.06, 0.10, 0.88, 0.73])
    ax.barh(range(len(top)), top.swing, color=ACCENT, height=0.4, zorder=2)
    ax.set_yticks([])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, top.swing.max() * 1.15)
    for i, (_, r) in enumerate(top.iterrows()):
        ax.text(0, i + 0.34, f"{r.posteam} vs {r.defteam}  ·  {clock(r)}  ·  {short_desc(r)}",
                fontsize=9, color=INK_2, va="bottom")
        ax.text(r.swing + top.swing.max() * 0.015, i, f"{r.swing:.0f} pts", fontsize=9.5,
                color=INK, va="center", fontweight="bold")
    ax.set_ylim(-0.6, len(top) - 0.1)
    ax.set_xlabel("Win probability swing (percentage points)")
    save(fig, out, "04_swing_plays.png")


def target_share(df, week, season, out):
    w = df[(df.week == week) & (df.play_type == "pass") & df.receiver_player_name.notna()]
    team_t = w.groupby("posteam").size()
    p = w.groupby(["receiver_player_name", "posteam"]).size().rename("tgt").reset_index()
    p["share"] = p.tgt / p.posteam.map(team_t) * 100
    top = p[p.tgt >= 6].sort_values("share", ascending=False).head(12).iloc[::-1]
    fig, ax = frame("Who's getting the ball?", "Share of team targets, min. 6 targets", week, season)
    ax.set_position([0.25, 0.10, 0.69, 0.73])
    ax.barh(range(len(top)), top.share, color=ACCENT, height=0.45, zorder=2)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{n}  {t}" for n, t in zip(top.receiver_player_name, top.posteam)],
                       fontsize=10, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, top.share.max() * 1.18)
    for i, (_, r) in enumerate(top.iterrows()):
        ax.text(r.share + 0.6, i, f"{r.share:.0f}%  ({r.tgt})", va="center", fontsize=9, color=INK_2)
    ax.set_xlabel("Target share (%)  ·  targets in parentheses")
    save(fig, out, "05_target_share.png")


def season_trend(df, week, season, out):
    s = scrimmage(df[df.week <= week])
    te = s.groupby(["posteam", "week"]).epa.mean().unstack()
    if week not in te.columns or week < 3:
        print("season trend skipped: need at least 3 weeks")
        return
    prior = te.drop(columns=week).mean(axis=1)
    delta = (te[week] - prior).dropna().sort_values(ascending=False)
    risers = list(delta.index[:3])
    roll = te.T.rolling(2, min_periods=1).mean().T   # 2-week rolling average
    fig, ax = frame("Heating up", f"Offense EPA per play, 2-week rolling average  ·  biggest Week {week} risers",
                    week, season, "Bye weeks carried over")
    roll = roll.ffill(axis=1)
    for team in roll.index:
        if team not in risers:
            ax.plot(roll.columns, roll.loc[team], color=NEUTRAL, lw=1, alpha=0.45, zorder=1)
    ends = {t: roll.loc[t, week] for t in risers}
    span = roll.max().max() - roll.min().min()
    gap, label_y, prev = span * 0.045, {}, None
    for t in sorted(ends, key=ends.get, reverse=True):   # keep end labels from colliding
        y = ends[t] if prev is None else min(ends[t], prev - gap)
        label_y[t] = prev = y
    for team, c in zip(risers, [ACCENT, ACCENT_2, ACCENT_3]):
        ax.plot(roll.columns, roll.loc[team], color=c, lw=2.5, zorder=3, label=team)
        ax.scatter([week], [ends[team]], color=c, s=60, edgecolor=SURFACE, lw=2, zorder=4)
        ax.text(week + 0.1, label_y[team], team, color=INK, fontsize=10,
                fontweight="bold", va="center")
    ax.axhline(0, color=INK_3, lw=1)
    ax.set_xticks(list(roll.columns))
    ax.set_xticklabels([f"Wk {c}" for c in roll.columns])
    ax.set_xlim(roll.columns.min() - 0.1, week + 0.5)
    ax.set_ylabel("Offense EPA per play")
    leg = ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK_2)
    save(fig, out, "06_heating_up.png")


CHARTS = [qb_scatter, team_tiers, game_of_week, swing_plays, target_share, season_trend]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--data", help="path to nflverse play-by-play CSV (optional)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    df = load(a.season, a.data)
    out = os.path.join(a.out, f"week_{a.week:02d}")
    os.makedirs(out, exist_ok=True)
    for chart in CHARTS:
        chart(df, a.week, a.season, out)


if __name__ == "__main__":
    main()
