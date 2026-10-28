# MoneyDown

Weekly NFL charts, power rankings with records against the spread, and
win-probability replays, built from
[nflverse](https://github.com/nflverse/nflverse-data) play-by-play data.

The site rebuilds itself every Tuesday at 11am Eastern, after Monday Night
Football, and publishes to GitHub Pages. You don't have to run anything.

## Launch (one time)

1. Create a new **public** repository on GitHub, for example `moneydown`.
2. Upload everything in this folder (keep the `.github` folder) and commit to `main`.
3. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Go to the **Actions** tab, open **Weekly update** and click **Run workflow**.
   It takes about 6 minutes. When it finishes, the site is live at
   `https://<your-username>.github.io/moneydown/`.

### Custom domain (moneydown.io)

1. In **Settings → Pages → Custom domain**, enter `moneydown.io` and save.
2. At your registrar, add these DNS records (and delete any parking or
   forwarding records it added):

   | Type | Host | Value |
   |---|---|---|
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | AAAA | @ | 2606:50c0:8000::153 |
   | AAAA | @ | 2606:50c0:8001::153 |
   | AAAA | @ | 2606:50c0:8002::153 |
   | AAAA | @ | 2606:50c0:8003::153 |
   | CNAME | www | `<your-username>.github.io` |

3. Tick **Enforce HTTPS** once it's available (can take up to an hour).

Link previews on X, Reddit and iMessage point at the domain in `brand.json`.
If you change domains, update it there.

## Renaming the site

Edit `brand.json`, then run the workflow again. The name updates on the page,
in every chart and in every video.

## Every week

Nothing. The workflow runs on Tuesday and adds the new week.

To pick the film-room game or write your own headline, edit `features.json`
before Tuesday (or run the workflow by hand afterward):

```json
{
  "8": {"game": "2026_08_BUF_KC", "title": "Buffalo finally gets Kansas City"}
}
```

`game` is the nflverse game ID (`season_week_AWAY_HOME`). Leave a week out and
the site picks the game with the biggest win-probability swings and uses the
final score as the headline.

## Run it on your own computer

```bash
pip install -r requirements.txt     # needs Python 3.10+ and ffmpeg
python update.py                    # downloads data, makes everything, builds site/
python -m http.server -d site 8000  # preview at http://localhost:8000
```

`python update.py --fresh` remakes every chart and video from scratch.

## What's in here

| File | What it does |
|---|---|
| `update.py` | Runs the whole weekly pipeline |
| `charts.py` | The six weekly charts (1080×1350, sized for social) |
| `rankings.py` | Power rankings table and its social image |
| `wp_video.py` | Vertical win-probability replay video (1080×1920) |
| `build_site.py` | Takeaways, film room and rankings data, writes `site/index.html` |
| `template.html` | The page design |
| `brand.json` | Site name, domain and tagline (change the name here) |
| `features.json` | Optional film-room picks and headlines |
| `.github/workflows/weekly.yml` | The Tuesday rebuild and deploy |

Charts and videos for social posts end up in `site/charts/week_XX/`. On
GitHub, open the finished **Weekly update** run and download **social-charts**
at the bottom of the page.
