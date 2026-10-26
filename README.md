# Yet I Will Rejoice

The website for *Yet I Will Rejoice*, a podcast from Dare Ministries hosted by Brandon Anderson. Live at https://yetiwillrejoice.org.

## How it works

- `data/episodes.json` holds every episode: YouTube id, title, series, episode number, co-host or guest, date and description.
- `tools/build.py` turns that file into the static site in `_site/` (home, episode library, one page per episode, about, ask a question, sitemap).
- `tools/sync_youtube.py` reads the YouTube channel's public feed and adds new uploads to `episodes.json`. It skips Shorts and fills in descriptions, dates and co-hosts that are missing.
- `.github/workflows/deploy.yml` runs the sync every morning, commits any new episodes, builds, and publishes to GitHub Pages. It also runs on every push and can be run by hand from the Actions tab.

## Common edits

Edit `data/episodes.json` on GitHub and commit. The site rebuilds in about a minute.

- **Fix a title, series or co-host:** change that episode's `title`, `series`, or `cohost`. The sync never overwrites a field that already has a value.
- **Hide a video** (a trailer, a recap): add its YouTube id to the `ignore` list.
- **Series keys:** `bible`, `apologetics`, `doctrine`, `living`, `sin`, `worldview`, `armor`, `guest`. Add a new series to the `series` list at the top.
- **Start here picks** on the home page: `START_HERE` in `tools/build.py`.

## Local preview

```sh
python3 tools/build.py --preview   # links point at index.html files so you can open _site/index.html directly
```

Never publish anything from the question form's responses: that sheet holds private submitter details.
