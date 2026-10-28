# MoneyDown

**NFL analytics, charted every week.** · [moneydown.io](https://moneydown.io)

MoneyDown turns each NFL week into a set of charts, a power ranking, and a
win-probability replay of the week's wildest game. Everything is built from
[nflverse](https://github.com/nflverse/nflverse-data) play-by-play data and
updates automatically every Tuesday after Monday Night Football.

## What's on the site

- **Power rankings.** All 32 teams ranked by net EPA per play, with offense,
  defense, pass, rush, success rate, recent form, and record against the
  spread. Color-coded and sortable.
- **Weekly charts.** QB efficiency, team tiers, game of the week, biggest
  swing plays, target share, and teams heating up. Each chart is sized for
  social (1080×1350).
- **Film room.** A vertical win-probability replay (1080×1920) of the game
  with the biggest swings, plus the four plays that decided it.
- **Archive.** Every week of the season, one click away.

## How it works

A GitHub Actions workflow runs every Tuesday at 11am Eastern:

1. Downloads the latest play-by-play data from nflverse.
2. Finds every finished week.
3. Generates any charts, rankings, and videos that don't exist yet.
4. Builds the site and deploys it to GitHub Pages.

## Methodology

| Metric | Definition |
|---|---|
| EPA | Expected points added: how much a play changed a team's expected score, given down, distance, and field position |
| Net EPA | Offense EPA per play minus defense EPA per play allowed. Not adjusted for opponent. |
| CPOE | Completion percentage over expected, based on throw depth, location, and pressure |
| Success rate | Share of plays with positive EPA |
| ATS | Record against the closing spread |
| Win probability | A team's chance of winning at any moment, from score, time, field position, and timeouts |

EPA, CPOE, and win probability come from the nflverse models. Regular-season
games only.

## Run locally

Requires Python 3.10+ and ffmpeg.

```bash
pip install -r requirements.txt
python update.py                    # download data, build charts, videos, and site/
python -m http.server -d site 8000  # preview at http://localhost:8000
```

Use `python update.py --fresh` to regenerate everything from scratch.

## Configuration

| File | Purpose |
|---|---|
| `brand.json` | Site name, domain, and tagline. Changing the name here updates the page, charts, and videos. |
| `features.json` | Optional. Picks the film-room game or sets a custom headline for a week. |

Example `features.json` entry:

```json
{
  "8": {"game": "2026_08_BUF_KC", "title": "Buffalo finally gets Kansas City"}
}
```

`game` is the nflverse game ID (`season_week_AWAY_HOME`). Weeks without an
entry use the game with the biggest win-probability swings and the final
score as the headline.

## Project structure

| File | Purpose |
|---|---|
| `update.py` | Runs the full weekly pipeline |
| `charts.py` | Weekly charts and shared chart styling |
| `rankings.py` | Power rankings data and social image |
| `wp_video.py` | Win-probability replay video |
| `build_site.py` | Chart takeaways, film room, rankings data, and `site/index.html` |
| `template.html` | Page layout and styles |
| `.github/workflows/weekly.yml` | Scheduled build and deploy |

## Credits

Data from [nflverse](https://github.com/nflverse/nflverse-data). MoneyDown is
an independent project and is not affiliated with the NFL or any team.

For entertainment and analysis only. Nothing here is betting advice.
