"""Test one newswire feed URL and say plainly whether it is usable.

A wire feed can fail in three ways, and only one of them is loud:

  * it errors — obvious;
  * it answers with something that is not a feed — obvious once you look;
  * it answers with a valid, well-formed, **empty** feed. This one is silent.
    Nothing throws, nothing logs, and the wire simply stops contributing while
    the dashboard stays green.

Feed URLs also rot. Wires retire endpoints and reissue tokenised ones, and the
machine that can check is the machine running the system — not wherever the
code was written. So this is a standalone probe you can point at a candidate
URL before committing to it:

    python -m app.probe_feed https://feed.businesswire.com/rss/home/?rss=XXXX

It prints the item count, the newest timestamp, and how many releases carry an
exchange-qualified ticker — the thing entity resolution actually needs. Once a
URL passes, put it in WIRE_FEED_URLS.
"""
from __future__ import annotations

import sys

from app.catalyst.entities import resolve_entity
from app.providers.base import ProviderError
from app.providers.wires import DEFAULT_WIRE_FEEDS, WireFeed, WireFirehoseProvider


def probe(url: str, *, label: str = "", fetch_bodies: int = 3,
          user_agent: str = "", quiet: bool = False) -> tuple[int, dict]:
    """Test one feed. Returns (exit code, summary) — 0 usable, 1 not."""
    feed = WireFeed(url=url, source=label or url)
    provider = WireFirehoseProvider(feeds=[feed], max_body_fetches=0,
                                    user_agent=user_agent)
    stats = {"url": url, "label": feed.source, "items": 0, "tagged": 0,
             "usable": False, "note": ""}

    def say(*args):
        if not quiet:
            print(*args)

    say(f"\n  {feed.source}\n  {url}\n" + "  " + "-" * 66)
    try:
        entries = provider._fetch_feed(feed)
    except ProviderError as exc:
        say(f"  UNUSABLE — the request failed: {exc}")
        stats["note"] = str(exc)[:80]
        return 1, stats

    if not entries:
        say("  UNUSABLE — the feed responded and parsed, but contains no items.")
        say("  This is the silent failure: nothing errors, and the wire simply")
        say("  contributes nothing. The URL is wrong or has been retired.")
        stats["note"] = "empty feed"
        return 1, stats

    stats["items"] = len(entries)
    dated = [e for e in entries if e.published_at_utc]
    newest = max((e.published_at_utc for e in dated), default=None)
    say(f"  {len(entries)} items"
        + (f", newest {newest:%Y-%m-%d %H:%M} UTC" if newest else ", no timestamps"))
    if not dated:
        say("  WARNING — no item carries a date, so the poller cannot tell new")
        say("  releases from old ones and will re-read the feed every sweep.")

    tagged = sum(1 for e in entries
                 if resolve_entity(headline=e.title, body=e.summary,
                                   known_companies={}).confidence >= 0.7)
    stats["tagged"] = tagged
    say(f"  {tagged}/{len(entries)} carry a ticker in the summary "
        f"({100.0 * tagged / len(entries):.0f}%)")

    if fetch_bodies:
        rescued = attempted = 0
        for entry in entries:
            if attempted >= fetch_bodies:
                break
            if resolve_entity(headline=entry.title, body=entry.summary,
                              known_companies={}).confidence >= 0.7:
                continue
            attempted += 1
            body = provider._fetch_body(entry.url)
            if body and resolve_entity(headline=entry.title, body=body,
                                       known_companies={}).confidence >= 0.7:
                rescued += 1
        stats["rescued"] = rescued
        stats["attempted"] = attempted
        if attempted:
            say(f"  of {attempted} without one, fetching the page found "
                f"{rescued} more")

    say("\n  Sample headlines:")
    for entry in entries[:3]:
        say(f"    · {entry.title[:90]}")

    say("\n  USABLE")
    stats["usable"] = True
    return 0, stats


def candidates(user_agent: str = "") -> int:
    """Test every known address for every wire, and rank what works.

    The useful column is the ticker rate, not the item count. GlobeNewswire's
    global feed returns plenty of releases and almost none of them are about a
    US-listed company, which is worse than useless: the pipeline reads, screens
    and discards them all sweep long.
    """
    from app.providers.wires import CANDIDATE_FEEDS

    results: list[dict] = []
    for source, urls in CANDIDATE_FEEDS.items():
        print(f"\n{'=' * 72}\n{source}\n{'=' * 72}")
        for url in urls:
            _, stats = probe(url, label=source, fetch_bodies=2,
                             user_agent=user_agent)
            results.append(stats)

    print(f"\n{'=' * 72}\nSUMMARY — pick the highest ticker rate, not the most items\n"
          f"{'=' * 72}")
    for source in CANDIDATE_FEEDS:
        rows = [r for r in results if r["label"] == source]
        print(f"\n{source}:")
        for row in rows:
            if not row["usable"]:
                print(f"  ✗  {row['note'][:52]:<54} {row['url'][:60]}")
                continue
            pct = 100.0 * row["tagged"] / row["items"]
            print(f"  ✓  {row['items']:>3} items, {pct:>3.0f}% tagged"
                  f"{'':<26} {row['url'][:60]}")

    usable = [r for r in results if r["usable"]]
    if not usable:
        print("\nNothing worked. Paste this output back — the addresses need "
              "revisiting, and SEC filings still run in the meantime.")
        return 1
    print("\nPut the winners in WIRE_FEED_URLS as: url|Source Name,url|Source Name")
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    user_agent = ""
    if "--user-agent" in args:
        i = args.index("--user-agent")
        user_agent = args[i + 1]
        del args[i:i + 2]

    if "--candidates" in args:
        return candidates(user_agent=user_agent)
    if not args:
        # No argument: test the built-in wires, which is what you want when
        # preflight has just said one of them is returning nothing.
        print("Probing the built-in wire feeds. Pass --candidates to test every "
              "known alternative, or a URL to test one.")
        return max(probe(f.url, label=f.source, user_agent=user_agent)[0]
                   for f in DEFAULT_WIRE_FEEDS)
    return max(probe(url, user_agent=user_agent)[0] for url in args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
