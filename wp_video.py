"""Animated win-probability video for one game.

Renders a vertical 1080x1920 MP4 (Reels / Shorts / TikTok) where the
win-probability line races through the game, slowing down for the finish and
pausing on the biggest swing plays.

Usage:
    python wp_video.py --week 5                      # auto-picks the wildest game
    python wp_video.py --week 5 --game 2026_05_PHI_JAX --title "Jacksonville walks it off"
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FFMpegWriter

from charts import (ACCENT, ACCENT_2, BRAND, FONT, GRID, INK, INK_2, INK_3, SURFACE, load)

FPS = 30
REAL = ["pass", "run", "field_goal", "punt", "kickoff", "extra_point", "qb_kneel", "qb_spike"]


def callout_text(r):
    yds = int(r.yards_gained) if pd.notna(r.yards_gained) else 0
    if r.play_type == "field_goal":
        res = {"made": "GOOD", "missed": "NO GOOD", "blocked": "BLOCKED"}.get(r.field_goal_result, str(r.field_goal_result).upper())
        return f"{r.kicker_player_name} {int(r.kick_distance)}-yd FG is {res}"
    if r.play_type == "kickoff" and pd.notna(r.kickoff_returner_player_name):
        return f"{r.kickoff_returner_player_name} {int(r.return_yards)}-yd kick return"
    if r.play_type == "punt" and pd.notna(r.punt_returner_player_name):
        return f"{r.punt_returner_player_name} {int(r.return_yards)}-yd punt return"
    if r.interception == 1:
        return f"{r.interception_player_name} picks off {r.passer_player_name}"
    if r.fumble_lost == 1:
        return f"{r.fumbled_1_player_name} fumble lost"
    td = " TD" if r.touchdown == 1 else ""
    if r.play_type == "pass" and pd.notna(r.receiver_player_name):
        return f"{r.passer_player_name} to {r.receiver_player_name}, {yds}-yd{td}"
    if r.play_type == "run" and pd.notna(r.rusher_player_name):
        return f"{r.rusher_player_name} {yds}-yd run{td}"
    return str(r.play_type).replace("_", " ").capitalize()


def clock_text(qtr, secs):
    q = "OT" if qtr >= 5 else f"Q{int(qtr)}"
    return f"{q}  {int(secs // 60)}:{int(secs % 60):02d}"


def build_timeline(end_t, stops, n_callout_pause=0.9, hold=3.0):
    """Game-time value (minutes) for every frame: quick through most of the
    game, slow over the final 5 minutes, brief pauses on key plays."""
    slow_from = max(end_t - 5, 0)
    fast = np.linspace(0, slow_from, int(8 * FPS), endpoint=False)
    slow = np.linspace(slow_from, end_t, int(7 * FPS))
    ts = np.concatenate([fast, slow])
    out, pending = [], sorted(stops)
    for t in ts:
        out.append(t)
        while pending and t >= pending[0]:
            out += [pending[0]] * int(n_callout_pause * FPS)
            pending.pop(0)
    out += [end_t] * int(hold * FPS)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--game", help="nflverse game_id; default = biggest total WP swing that week")
    ap.add_argument("--title", help="headline; default is the final score")
    ap.add_argument("--data")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    df = load(a.season, a.data)
    wk = df[df.week == a.week]
    gid = a.game or wk[wk.wpa.notna()].groupby("game_id").wpa.apply(lambda s: s.abs().sum()).idxmax()
    full = df[df.game_id == gid].sort_values("play_id")
    g = full[full.play_type.isin(REAL) & full.home_wp.notna()].copy()
    home, away = g.home_team.iloc[0], g.away_team.iloc[0]
    g["t"] = np.where(g.qtr <= 4, (3600 - g.game_seconds_remaining) / 60,
                      (3600 + 600 - g.quarter_seconds_remaining) / 60)
    sign = np.where(g.posteam == home, 1, -1)
    post = g.home_wp_post if "home_wp_post" in g else g.home_wp + g.wpa * sign
    g["wp_post"] = post.fillna(g.home_wp + g.wpa.fillna(0) * sign).clip(0, 1) * 100
    g["hs"] = g.total_home_score.astype(int)
    g["as"] = g.total_away_score.astype(int)
    last = full.iloc[-1]
    hs, as_ = int(last.total_home_score), int(last.total_away_score)
    if not a.title:
        ot = " in OT" if g.qtr.max() >= 5 else ""
        a.title = (f"{home} {hs}, {away} {as_}" if hs >= as_ else f"{away} {as_}, {home} {hs}") + ot
    end_t = max(g.t.max(), 60)
    final_wp = 100.0 if hs > as_ else 0.0 if hs < as_ else 50.0

    xs = np.concatenate([[0], g.t.values, [end_t]])
    ys = np.concatenate([[g.home_wp.iloc[0] * 100], g.wp_post.values, [final_wp]])

    keys = g.reindex(g.wpa.abs().sort_values(ascending=False).index).head(5).sort_values("t")
    timeline = build_timeline(end_t, list(keys.t))

    # ------------------------------------------------------------ layout
    fig = plt.figure(figsize=(9, 16), dpi=120)
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.07, 0.955, BRAND, fontsize=17, fontweight="bold", color=ACCENT, family=FONT)
    fig.text(0.93, 0.955, f"WEEK {a.week}  ·  {a.season}", fontsize=15, color=INK_2, ha="right", family=FONT)
    fig.text(0.07, 0.905, a.title, fontsize=34, fontweight="bold", color=INK, family=FONT)
    fig.text(0.07, 0.875, f"{away} at {home}  ·  live win probability", fontsize=17, color=INK_2, family=FONT)

    score_away = fig.text(0.07, 0.79, "", fontsize=58, fontweight="bold", color=INK, family=FONT)
    score_home = fig.text(0.93, 0.79, "", fontsize=58, fontweight="bold", color=INK, ha="right", family=FONT)
    fig.text(0.07, 0.765, away, fontsize=18, color=ACCENT_2, fontweight="bold", family=FONT)
    fig.text(0.93, 0.765, home, fontsize=18, color=ACCENT, fontweight="bold", ha="right", family=FONT)
    clock = fig.text(0.5, 0.80, "", fontsize=20, color=INK_2, ha="center", family=FONT)

    ax = fig.add_axes([0.12, 0.30, 0.80, 0.42])
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlim(0, end_t)
    ax.set_ylim(0, 100)
    ax.axhline(50, color=INK_3, lw=1.2)
    for q in [15, 30, 45, 60]:
        if q < end_t:
            ax.axvline(q, color=GRID, lw=1)
    ticks = [7.5, 22.5, 37.5, 52.5] + ([65] if end_t > 60 else [])
    ax.set_xticks(ticks)
    ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4", "OT"][:len(ticks)], fontsize=14, color=INK_3)
    ax.set_yticks([0, 50, 100])
    ax.set_yticklabels([f"{away}\n100%", "50%", f"{home}\n100%"], fontsize=13, color=INK_3)
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID, lw=0.6)

    line, = ax.plot([], [], color=INK, lw=3, zorder=4)
    dot = ax.scatter([], [], s=140, color=INK, edgecolor=SURFACE, lw=3, zorder=5)
    fills = []

    pct = fig.text(0.5, 0.235, "", fontsize=30, fontweight="bold", color=INK, ha="center", family=FONT)
    card = fig.text(0.5, 0.15, "", fontsize=21, color=INK, ha="center", va="center", family=FONT,
                    bbox=dict(boxstyle="round,pad=0.8", fc="#24241f", ec=GRID, lw=1.5), visible=False)
    fig.text(0.07, 0.035, "Data: nflverse play-by-play", fontsize=12, color=INK_3, family=FONT)

    def draw(t):
        for f in fills:
            f.remove()
        fills.clear()
        mask = xs <= t
        x, y = xs[mask], ys[mask]
        line.set_data(x, y)
        dot.set_offsets([[x[-1], y[-1]]])
        if len(x) > 1:
            fills.append(ax.fill_between(x, 50, y, where=y >= 50, color=ACCENT, alpha=0.3, lw=0,
                                         interpolate=True, step=None))
            fills.append(ax.fill_between(x, 50, y, where=y < 50, color=ACCENT_2, alpha=0.3, lw=0,
                                         interpolate=True))
        done = t >= end_t and mask.all()
        past = g[g.t <= t]
        if done:
            score_home.set_text(str(hs)); score_away.set_text(str(as_)); clock.set_text("FINAL")
        elif len(past):
            r = past.iloc[-1]
            score_home.set_text(str(r.hs)); score_away.set_text(str(r["as"]))
            clock.set_text(clock_text(r.qtr, r.quarter_seconds_remaining))
        else:
            score_home.set_text("0"); score_away.set_text("0"); clock.set_text("Q1  15:00")
        wp = y[-1]
        lead, val = (home, wp) if wp >= 50 else (away, 100 - wp)
        pct.set_text(f"{lead} win chance  {val:.0f}%" if not done else f"{home if hs > as_ else away} wins")
        pct.set_color(ACCENT if lead == home else ACCENT_2)
        hit = keys[keys.t <= t]
        if len(hit):
            r = hit.iloc[-1]
            swing = abs(r.wpa) * 100
            card.set_text(f"{r.posteam}  ·  {clock_text(r.qtr, r.quarter_seconds_remaining)}\n"
                          f"{callout_text(r)}\nWin chance swing: {swing:.0f} pts")
            card.set_visible(True)

    os.makedirs(os.path.join(a.out, f"week_{a.week:02d}"), exist_ok=True)
    path = os.path.join(a.out, f"week_{a.week:02d}", f"wp_{gid}.mp4")
    writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=6000,
                          extra_args=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    with writer.saving(fig, path, dpi=120):
        for t in timeline:
            draw(t)
            writer.grab_frame(facecolor=SURFACE)
    print("saved", path, f"({len(timeline) / FPS:.1f}s)")


if __name__ == "__main__":
    main()
