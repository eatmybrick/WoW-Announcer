# WoW Forever Discord announcer

Posts new WoW Forever news and patch notes to a Discord channel. Patch and build posts get an orange embed, everything else is blue.

## Setup

1. In Discord open the channel settings, go to Integrations, then Webhooks, make a new webhook and copy the URL.
2. Run it:

```
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 wowforever_news.py --dry-run     # see what it would post
python3 wowforever_news.py               # one check
python3 wowforever_news.py --loop 900    # check every 15 minutes
```

Python 3.8+ and nothing to install.

On the first real run it marks everything already in the feed as seen so your channel is not flooded. Pass `--backfill 3` if you want the latest 3 announced right away.

## Running it on a schedule

Cron every 15 minutes:

```
*/15 * * * * DISCORD_WEBHOOK_URL="..." /usr/bin/python3 /path/to/wowforever_news.py >> /tmp/wowforever.log 2>&1
```

Or leave `--loop 900` running in a tmux session, a systemd service or a small container. The loop never polls faster than every 5 minutes.

## Source

Default feed is the Wowhead WoW Forever RSS feed (`https://www.wowhead.com/forever/news/rss/forever`). It covers Blizzard dev notes, hotfixes and maintenance posts plus Wowhead's own news. Override with `--feed` or `FOREVER_FEED_URL` for any other RSS feed. `--category ""` posts every item in the feed instead of only the Forever ones.

The posted state lives in `seen.json` next to the script. Delete it to reset.
