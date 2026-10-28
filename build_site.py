"""Build the website from the generated charts.

Copies each week's charts and video into the site folder, computes a takeaway
for every chart, the power rankings and the film-room feature, then writes
site/index.html (a complete page ready for GitHub Pages).

Usage:
    python build_site.py --weeks 1 2 3 4 5 6 7
    python build_site.py --all                 # every week that has charts in out/

Optional: features.json next to this script overrides the film-room headline
and blurb for a week, e.g. {"7": {"title": "Giants win it in overtime"}}.
"""

import argparse
import html
import json
import os
import shutil
import subprocess

import pandas as pd

from charts import BRAND_INFO, clock, load, scrimmage, short_desc
from rankings import table as rankings_table

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_URL = os.environ.get("SITE_URL") or f"https://{BRAND_INFO['domain']}"  # used for link previews

TAGS = {
    "00_power_rankings.png": ("Power rankings", "Teams"),
    "01_qb_efficiency.png": ("Who actually played well?", "Quarterbacks"),
    "02_team_tiers.png": ("Team tiers", "Teams"),
    "03_game_of_the_week.png": ("Game of the week", "Games"),
    "04_swing_plays.png": ("Biggest swing plays", "Games"),
    "05_target_share.png": ("Who's getting the ball?", "Receivers"),
    "06_heating_up.png": ("Heating up", "Teams"),
}
REAL = ["pass", "run", "field_goal", "punt", "kickoff", "extra_point", "qb_kneel", "qb_spike"]


def final_score(df, gid):
    last = df[df.game_id == gid].iloc[-1]
    return last.home_team, last.away_team, int(last.total_home_score), int(last.total_away_score)


def wildest_game(w):
    return w[w.wpa.notna()].groupby("game_id").wpa.apply(lambda x: x.abs().sum()).idxmax()


def takeaways(df, week):
    w = df[df.week == week]
    out = {}

    qb = w[(w.qb_dropback == 1) & w.epa.notna()].groupby(["passer_player_name", "posteam"]) \
        .agg(n=("epa", "size"), epa=("epa", "mean"), cpoe=("cpoe", "mean")).reset_index()
    q = qb[qb.n >= 20].sort_values("epa", ascending=False).iloc[0]
    out["01_qb_efficiency.png"] = (f"{q.passer_player_name} ({q.posteam}) led all quarterbacks at "
                                   f"{q.epa:+.2f} EPA per dropback, completing {q.cpoe:+.1f}% over expected.")

    s = scrimmage(w)
    t = pd.DataFrame({"off": s.groupby("posteam").epa.mean(), "def": s.groupby("defteam").epa.mean()}).dropna()
    t["net"] = t.off - t["def"]
    best = t.sort_values("net", ascending=False).index[0]
    top_off = t.off.idxmax()
    out["02_team_tiers.png"] = (f"{best} had the best net EPA of the week. {top_off} had the top offense "
                                f"at {t.off.max():+.2f} per play.")

    gid = wildest_game(w)
    home, away, hs, as_ = final_score(df, gid)
    win, lose, ws, ls = (home, away, hs, as_) if hs >= as_ else (away, home, as_, hs)
    g = w[(w.game_id == gid) & w.wpa.notna()]
    k = g.loc[g.wpa.abs().idxmax()]
    out["03_game_of_the_week.png"] = (f"{win} {ws}, {lose} {ls}. The biggest moment: "
                                      f"{short_desc(k)} ({clock(k)}).")

    p = w[w.wpa.notna() & w.posteam.notna()]
    r = p.loc[p.wpa.abs().idxmax()]
    out["04_swing_plays.png"] = (f"{r.posteam}, {clock(r)}: {short_desc(r)} moved win chance "
                                 f"{abs(r.wpa) * 100:.0f} points in one snap.")

    tg = w[(w.play_type == "pass") & w.receiver_player_name.notna()]
    tt = tg.groupby("posteam").size()
    rs = tg.groupby(["receiver_player_name", "posteam"]).size().rename("n").reset_index()
    rs["share"] = rs.n / rs.posteam.map(tt) * 100
    top = rs[rs.n >= 6].sort_values("share", ascending=False).iloc[0]
    out["05_target_share.png"] = (f"{top.receiver_player_name} drew {top.share:.0f}% of {top.posteam}'s "
                                  f"targets ({top.n} total).")

    if week >= 3:
        te = scrimmage(df[df.week <= week]).groupby(["posteam", "week"]).epa.mean().unstack()
        if week in te.columns:
            d = (te[week] - te.drop(columns=week).mean(axis=1)).dropna().sort_values(ascending=False)
            r3 = list(d.index[:3])
            out["06_heating_up.png"] = (f"{', '.join(r3[:2])} and {r3[2]} showed the biggest offensive "
                                        f"jumps over their season average.")
    return out


def feature(df, week, gid, overrides):
    """Film-room copy and the four plays that decided the game."""
    home, away, hs, as_ = final_score(df, gid)
    g = df[(df.game_id == gid) & df.play_type.isin(REAL) & df.wpa.notna()].sort_values("play_id")
    ot = g.qtr.max() >= 5
    win, lose, ws, ls = (home, away, hs, as_) if hs >= as_ else (away, home, as_, hs)
    side = (g.home_wp >= 0.5).astype(int)
    flips = int((side.diff().abs() == 1).sum())
    text = (f"{win} beat {lose} {ws}-{ls}{' in overtime' if ot else ''}. The win probability line changed "
            f"hands {flips} times. Watch every swing.")
    keys = g.reindex(g.wpa.abs().sort_values(ascending=False).index).head(4).sort_values("play_id")
    plays = []
    for _, r in keys.iterrows():
        gainer = r.posteam if r.wpa > 0 else r.defteam
        plays.append({"clock": clock(r), "text": short_desc(r), "team": gainer,
                      "swing": round(abs(r.wpa) * 100)})
    o = overrides.get(str(week), {})
    return {"title": o.get("title", f"{win} {ws}, {lose} {ls}"), "text": o.get("text", text), "plays": plays}


def poster(video_path, out_path):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-sseof", "-1.5", "-i", video_path,
                    "-frames:v", "1", "-vf", "scale=540:-1", "-q:v", "4", out_path], check=True)


def brand(text):
    """Fill {{NAME}}, {{NAME_UPPER}}, {{DOMAIN}} and {{TAGLINE}} from brand.json."""
    for k, v in {"NAME": BRAND_INFO["name"], "NAME_UPPER": BRAND_INFO["name"].upper(),
                 "DOMAIN": BRAND_INFO["domain"], "TAGLINE": BRAND_INFO["tagline"]}.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def page(manifest, latest):
    """Wrap template.html in a full document with link-preview tags."""
    with open(os.path.join(HERE, "template.html")) as fh:
        body = fh.read().replace("/*MANIFEST*/null", json.dumps(manifest, separators=(",", ":")))
    body = brand(body)
    title_tag = body.split("</title>")[0] + "</title>"
    body = body[len(title_tag):]
    desc = (f"NFL Week {latest['week']} in charts: QB efficiency, team tiers, power rankings, "
            f"win probability and more, built from play-by-play data.")
    share = next((c["src"] for c in latest["charts"] if "power_rankings" in c["src"]), latest["charts"][0]["src"])
    img = f"{SITE_URL.rstrip('/')}/{share}" if SITE_URL else share
    head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{title_tag}
<meta name="description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{BRAND_INFO['name']} · Week {latest['week']} in charts">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#121311">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
</head>
<body>
"""
    return head + body + "\n</body>\n</html>\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--data")
    ap.add_argument("--charts", default="out")
    ap.add_argument("--site", default="site")
    a = ap.parse_args()
    if a.all or not a.weeks:
        a.weeks = sorted(int(d[5:]) for d in os.listdir(a.charts) if d.startswith("week_"))
    df = load(a.season, a.data)
    overrides = {}
    fpath = os.path.join(HERE, "features.json")
    if os.path.exists(fpath):
        with open(fpath) as fh:
            overrides = json.load(fh)

    manifest = {"season": a.season, "weeks": []}
    for wk in sorted(a.weeks):
        src = os.path.join(a.charts, f"week_{wk:02d}")
        dst = os.path.join(a.site, "charts", f"week_{wk:02d}")
        os.makedirs(dst, exist_ok=True)
        w = df[df.week == wk]
        notes = takeaways(df, wk)
        ranks = rankings_table(df, wk)
        notes["00_power_rankings.png"] = (f"{ranks[0]['team']} sits first in net EPA per play "
                                          f"({ranks[0]['net']:+.2f}). Full sortable table above.")
        items = []
        for f in sorted(os.listdir(src)):
            if f in TAGS:
                shutil.copy(os.path.join(src, f), os.path.join(dst, f))
                title, tag = TAGS[f]
                items.append({"src": f"charts/week_{wk:02d}/{f}", "title": title, "tag": tag,
                              "note": notes.get(f, "")})
        video = None
        for f in sorted(os.listdir(src)):
            if f.endswith(".mp4"):
                shutil.copy(os.path.join(src, f), os.path.join(dst, f))
                gid = f[3:-4]
                poster(os.path.join(dst, f), os.path.join(dst, "wp_poster.jpg"))
                video = {"src": f"charts/week_{wk:02d}/{f}", "poster": f"charts/week_{wk:02d}/wp_poster.jpg",
                         **feature(df, wk, gid, overrides)}
        dates = sorted(w.game_date.unique())
        manifest["weeks"].append({"week": wk, "games": int(w.game_id.nunique()), "first": dates[0],
                                  "last": dates[-1], "charts": items, "video": video, "rankings": ranks})

    shutil.copy(os.path.join(HERE, "favicon.svg"), os.path.join(a.site, "favicon.svg"))
    open(os.path.join(a.site, ".nojekyll"), "w").close()
    with open(os.path.join(a.site, "manifest.json"), "w") as fh:
        json.dump(manifest, fh)
    with open(os.path.join(a.site, "index.html"), "w") as fh:
        fh.write(page(manifest, manifest["weeks"][-1]))
    print("built site for weeks", [w["week"] for w in manifest["weeks"]])


if __name__ == "__main__":
    main()
