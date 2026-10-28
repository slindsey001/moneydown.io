"""One command to refresh the whole site.

Downloads the latest play-by-play, finds every finished week, makes any charts,
rankings and game-of-the-week videos that are missing, and rebuilds site/.

    python update.py              # normal weekly run
    python update.py --fresh      # remake everything from scratch
"""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(*args):
    print("+", " ".join(args), flush=True)
    subprocess.run([PY, *args], check=True, cwd=HERE)


def finished_weeks(df, today):
    """A week counts once every game is over and Monday night is in the books."""
    done = []
    for wk, w in df.groupby("week"):
        ended = w.groupby("game_id").desc.last().eq("END GAME").all()
        last = pd.Timestamp(w.game_date.max()).date()
        if ended and (last.weekday() in (0, 1) or (today - last).days >= 2):
            done.append(int(wk))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--fresh", action="store_true", help="delete old charts and videos first")
    a = ap.parse_args()

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    data = os.path.join(HERE, "data", f"pbp_{a.season}.csv.gz")
    url = f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{a.season}.csv.gz"
    print("downloading", url, flush=True)
    urllib.request.urlretrieve(url, data)

    df = pd.read_csv(data, low_memory=False)
    df = df[df.season_type == "REG"]
    weeks = finished_weeks(df, dt.date.today())
    print("finished weeks:", weeks)
    out = os.path.join(HERE, "out")
    if a.fresh and os.path.isdir(out):
        shutil.rmtree(out)

    overrides = {}
    fpath = os.path.join(HERE, "features.json")
    if os.path.exists(fpath):
        with open(fpath) as fh:
            overrides = json.load(fh)

    for wk in weeks:
        d = os.path.join(out, f"week_{wk:02d}")
        if not os.path.exists(os.path.join(d, "01_qb_efficiency.png")):
            run("charts.py", "--week", str(wk), "--data", data, "--out", out)
        if not os.path.exists(os.path.join(d, "00_power_rankings.png")):
            run("rankings.py", "--week", str(wk), "--data", data, "--out", out)
        if not any(f.endswith(".mp4") for f in os.listdir(d)):
            o = overrides.get(str(wk), {})
            args = ["wp_video.py", "--week", str(wk), "--data", data, "--out", out]
            if o.get("game"):
                args += ["--game", o["game"]]
            if o.get("title"):
                args += ["--title", o["title"]]
            run(*args)

    run("build_site.py", "--weeks", *map(str, weeks), "--data", data, "--charts", out,
        "--site", os.path.join(HERE, "site"))


if __name__ == "__main__":
    main()
