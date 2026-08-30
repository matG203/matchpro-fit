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


def probe(url: str, *, label: str = "", fetch_bodies: int = 3) -> int:
    """Returns a process exit code: 0 usable, 1 not."""
    feed = WireFeed(url=url, source=label or url)
    provider = WireFirehoseProvider(feeds=[feed], max_body_fetches=0)

    print(f"\n  {feed.source}\n  {url}\n" + "  " + "-" * 66)
    try:
        entries = provider._fetch_feed(feed)
    except ProviderError as exc:
        print(f"  UNUSABLE — the request failed: {exc}")
        return 1

    if not entries:
        print("  UNUSABLE — the feed responded and parsed, but contains no items.")
        print("  This is the silent failure: nothing errors, and the wire simply")
        print("  contributes nothing. The URL is wrong or has been retired.")
        return 1

    dated = [e for e in entries if e.published_at_utc]
    newest = max((e.published_at_utc for e in dated), default=None)
    print(f"  {len(entries)} items"
          + (f", newest {newest:%Y-%m-%d %H:%M} UTC" if newest else ", no timestamps"))
    if not dated:
        print("  WARNING — no item carries a date, so the poller cannot tell new")
        print("  releases from old ones and will re-read the feed every sweep.")

    tagged = sum(1 for e in entries
                 if resolve_entity(headline=e.title, body=e.summary,
                                   known_companies={}).confidence >= 0.7)
    print(f"  {tagged}/{len(entries)} carry a ticker in the summary "
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
        if attempted:
            print(f"  of {attempted} without one, fetching the page found "
                  f"{rescued} more")

    print("\n  Sample headlines:")
    for entry in entries[:3]:
        print(f"    · {entry.title[:90]}")

    print("\n  USABLE")
    return 0


def main(argv: list[str]) -> int:
    urls = argv[1:]
    if not urls:
        # No argument: test the built-in wires, which is what you want when
        # preflight has just said one of them is returning nothing.
        print("Probing the built-in wire feeds. Pass a URL to test a specific one.")
        return max(probe(f.url, label=f.source) for f in DEFAULT_WIRE_FEEDS)
    return max(probe(url) for url in urls)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
