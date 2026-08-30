"""Catalyst dashboard pages (spec §99-101)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.catalyst_routes import event_detail, ingestion, lead_time, live_catalysts
from app.api.dashboard import _page, _pct

router = APIRouter()

# A wire nobody has asked yet is not a wire that failed. Showing three red
# lights for the first thirty seconds after every restart teaches the operator
# to ignore red lights.
_FEED_STATE = {"ok": "🟢", "failing": "🔴", "unpolled": "⚪"}
_FEED_NOTE = {"unpolled": "not polled yet — the first sweep runs within "
                          "CATALYST_POLL_SECONDS of startup"}

# What each ingest outcome means, in the order a reader should scan them.
_OUTCOME_STYLE = {
    "alerted": ("🚨", "#2fbf71"),
    "scored": ("🟡", "#d7a63b"),
    "screened_out": ("·", "#8a929b"),
    "clustered": ("·", "#8a929b"),
    "no_entity": ("·", "#6b7280"),
}


def _score_marker(score: float) -> str:
    if score >= 9.5:
        return "🔥"
    if score >= 9.0:
        return "🚨"
    if score >= 8.0:
        return "🟢"
    if score >= 7.0:
        return "🟡"
    return "⚪"


def _bar(value: float | None) -> str:
    """Compact 0-10 meter — quicker to scan than a column of numbers."""
    if value is None:
        return "<span class='sub'>—</span>"
    filled = max(0, min(10, round(value)))
    colour = "#2fbf71" if value >= 8 else "#d7a63b" if value >= 6 else "#8a929b"
    return (f"<span title='{value:.1f}/10' style='color:{colour};"
            f"font-family:ui-monospace,monospace'>{'█' * filled}{'·' * (10 - filled)}</span>"
            f" <span class='sub'>{value:.1f}</span>")


@router.get("/catalysts", response_class=HTMLResponse)
def catalysts_page() -> HTMLResponse:
    data = live_catalysts(limit=40)
    rows = data["catalysts"]

    if not rows:
        table = ("<div class='card'><div class='empty'>No catalysts scored yet. "
                 "Items that fail the screen are recorded but never scored — "
                 "see the <a href='/news'>news evidence</a> page for what has "
                 "been read and why it was discarded.</div></div>")
    else:
        body = "".join(
            f"<tr>"
            f"<td class='tick'>{r['ticker']}</td>"
            f"<td>{r['event_type'].replace('_', ' ')}</td>"
            f"<td class='score'>{_score_marker(r['upside_catalyst_score'])} "
            f"{r['upside_catalyst_score']:.1f}</td>"
            f"<td>{_bar(r['catalyst_strength'])}</td>"
            f"<td>{_bar(r['surprise_novelty'])}</td>"
            f"<td>{_bar(r['move_amplification'])}</td>"
            f"<td>{_bar(r['reaction_room'])}</td>"
            f"<td>{_pct(r['abnormal_move_pct'])}</td>"
            f"<td>{r['first_public_london'] or '—'}</td>"
            f"<td><a href='/catalysts/{r['event_id']}'>detail</a></td>"
            f"</tr>"
            for r in rows)
        table = (
            "<div class='card'><table>"
            "<tr><th>Ticker</th><th>Event</th><th>Score</th><th>Strength</th>"
            "<th>Surprise</th><th>Amplification</th><th>Reaction room</th>"
            "<th>Abnormal move</th><th>First public</th><th></th></tr>"
            f"{body}</table></div>")

    return _page("Catalyst Sentinel", f"""
      <p class='sub'><a href='/'>← Earnings Sentinel</a></p>
      <h1>Catalyst Sentinel</h1>
      <p class='sub'>Non-earnings catalysts · all times Europe/London ·
        <a href='/news'>news evidence</a> ·
        <a href='/api/catalyst/performance'>calibration</a></p>
      <h2>Live catalysts</h2>{table}
      <p class='sub'>High scores are designed to be rare. Zero alerts on a given
        day is a valid outcome, not a fault.</p>
    """)


@router.get("/catalysts/{event_id}", response_class=HTMLResponse)
def catalyst_detail_page(event_id: int) -> HTMLResponse:
    data = event_detail(event_id)
    event = data["event"]
    scores = data["scores"] or {}
    impact = data["economic_impact"] or {}
    structure = data["market_structure"] or {}
    reaction = data["price_reaction"] or {}
    review = data["adversarial_review"] or {}

    stats = "".join(
        f"<div class='stat'><div class='k'>{label}</div><div class='v'>{value}</div></div>"
        for label, value in [
            ("Upside catalyst", f"{scores.get('upside_catalyst_score', 0):.1f}"
             if scores else "—"),
            ("Catalyst strength", f"{scores.get('catalyst_strength', 0):.1f}" if scores else "—"),
            ("Surprise & novelty", f"{scores.get('surprise_novelty', 0):.1f}" if scores else "—"),
            ("Move amplification", f"{scores.get('move_amplification', 0):.1f}"
             if scores else "—"),
            ("Reaction room", f"{scores.get('reaction_room', 0):.1f}" if scores else "—"),
            ("Confidence", f"{scores.get('confidence', 0):.1f}" if scores else "—"),
        ])

    def bullets(items, empty: str) -> str:
        if not items:
            return f"<p class='sub'>{empty}</p>"
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"

    offsets = data["negative_offsets"]
    offsets_html = ("<p class='sub'>None detected.</p>" if not offsets else
                    "<ul>" + "".join(
                        f"<li><strong>{o['severity']:.1f}</strong> — {o['description']}"
                        f"<span class='sub'> ({o['detected_by']})</span></li>"
                        for o in offsets) + "</ul>")

    facts_html = ("<p class='sub'>No structured facts extracted.</p>"
                  if not data["facts"] else
                  "<div class='card'><table><tr><th>Fact</th><th>Value</th><th>Quote</th></tr>"
                  + "".join(
                      f"<tr><td>{f['name']}</td><td>{f['value_text']}</td>"
                      f"<td class='sub'>{(f['quote'] or '')[:160]}</td></tr>"
                      for f in data["facts"]) + "</table></div>")

    sources_html = "".join(
        f"<li><a href='{s['url']}'>{s['provider'] or s['tier']}</a> "
        f"<span class='sub'>{s['tier']}</span></li>" for s in data["sources"])

    timeline_html = "".join(
        f"<tr><td>{t['at']}</td><td>{t['stage']}</td>"
        f"<td>{t['duration_ms']:.0f} ms</td><td class='sub'>{t['detail'][:120]}</td></tr>"
        for t in data["timeline"])

    caps = scores.get("caps_applied") or []

    return _page(f"{event['ticker']} — Catalyst", f"""
      <p class='sub'><a href='/catalysts'>← catalysts</a></p>
      <h1>{event['ticker']} · {event['event_type'].replace('_', ' ')}</h1>
      <p class='sub'>{event['headline']}</p>
      <p class='sub'>First public {event['first_public_london'] or 'unknown'} ·
        certainty {event['certainty']} · half-life {event['half_life']} ·
        {event['cluster_members']} source(s) · state {event['state']}</p>

      <div class='grid'>{stats}</div>

      <h2>Caps and gates applied</h2>
      {bullets(caps, 'No caps applied — score is the raw weighted result.')}

      <h2>What is actually new</h2>
      <p>{(data['what_is_new'] or {}).get('information_delta', '—')}</p>
      <p class='sub'>Previously known: {review.get('previously_known_information') or '—'}</p>

      <h2>Economic impact</h2>
      <div class='card'><table>
        <tr><th>Headline</th><th>Guaranteed</th><th>Expected</th>
            <th>% revenue</th><th>% market cap</th><th>Basis</th></tr>
        <tr><td>{_money(impact.get('headline_value'))}</td>
            <td>{_money(impact.get('guaranteed_value'))}</td>
            <td>{_money(impact.get('expected_value'))}</td>
            <td>{_ratio(impact.get('value_to_revenue'))}</td>
            <td>{_ratio(impact.get('value_to_market_cap'))}</td>
            <td class='sub'>{impact.get('basis', '—')}</td></tr>
      </table></div>
      <p class='sub'>{impact.get('notes', '')}</p>

      <h2>Why it might not move</h2>{offsets_html}

      <h2>Adversarial review</h2>
      {bullets(review.get('findings'), 'No adversarial review recorded.')}

      <h2>Market structure</h2>
      <div class='card'><table>
        <tr><th>Market cap</th><th>Free float</th><th>Short % float</th>
            <th>RVOL</th><th>Spread</th><th>Session</th><th>Halt</th></tr>
        <tr><td>{_money(structure.get('market_cap'))}</td>
            <td>{_num(structure.get('free_float_shares'))}</td>
            <td>{_ratio_pct(structure.get('short_percent_float'))}</td>
            <td>{_num(structure.get('relative_volume'))}</td>
            <td>{_ratio_pct(structure.get('spread_pct'))}</td>
            <td>{structure.get('session', '—')}</td>
            <td>{structure.get('halt_state', '—')}</td></tr>
      </table></div>

      <h2>Price reaction</h2>
      <div class='card'><table>
        <tr><th>Pre-event run-up</th><th>Move since disclosure</th><th>Abnormal</th>
            <th>× normal move</th><th>Analogue expectation</th></tr>
        <tr><td>{_pct(reaction.get('pre_event_runup_pct'))}</td>
            <td>{_pct(reaction.get('move_since_disclosure_pct'))}</td>
            <td>{_pct(reaction.get('abnormal_move_pct'))}</td>
            <td>{_num(reaction.get('move_multiple'))}</td>
            <td>{_ratio_pct(reaction.get('analogue_expected_move_pct'))}</td></tr>
      </table></div>
      <p class='sub'>{reaction.get('notes', '')}</p>

      <h2>Extracted facts</h2>{facts_html}

      <h2>Sources</h2><div class='card'><ul>{sources_html or '<li>—</li>'}</ul></div>

      <h2>Pipeline timeline</h2>
      <div class='card'><table>
        <tr><th>At</th><th>Stage</th><th>Duration</th><th>Detail</th></tr>
        {timeline_html}
      </table></div>

      <p class='sub'>Scoring model {scores.get('model_version', '—')}</p>
    """)


@router.get("/news", response_class=HTMLResponse)
def news_evidence_page(request: Request, hours: int = 24) -> HTMLResponse:
    """News → alert evidence.

    Deliberately shows the discards as well as the alerts. A page that listed
    only the hits would be a highlight reel; the ratio between them is the
    thing worth knowing, and so is a wire that has quietly stopped answering.
    """
    container = getattr(request.app.state, "container", None)
    digest = ingestion(hours=hours, limit=120, container=container)
    lead = lead_time(limit=40, container=container)

    # ── are the feeds alive? ──
    if not digest["feeds"]:
        feeds_html = ("<div class='card'><div class='empty'>No newswire feeds are "
                      "configured. Catalyst detection is running on SEC filings "
                      "alone, which sees most news only once it is 8-K'd — often "
                      "hours later. Set <code>WIRE_FEEDS_ENABLED=true</code>."
                      "</div></div>")
    else:
        rows = "".join(
            f"<tr><td>{_FEED_STATE.get(f['state'], '🔴')} {f['source']}</td>"
            f"<td>{f['items_last_sweep']}</td>"
            f"<td>{f['new_last_sweep']}</td>"
            f"<td>{_age(f['newest_item_age_minutes'])}</td>"
            f"<td class='sub'>{f['last_success_london'] or 'never'}</td>"
            f"<td class='sub'>{f['error'][:90] or _FEED_NOTE.get(f['state'], '')}</td></tr>"
            for f in digest["feeds"])
        feeds_html = (
            "<div class='card'><table>"
            "<tr><th>Wire</th><th>Items last sweep</th><th>New</th>"
            "<th>Newest release</th><th>Last success</th><th>Status</th></tr>"
            f"{rows}</table></div>")

    sweep = digest["last_sweep"]
    sweep_html = ("<p class='sub'>No sweep has run yet.</p>" if not sweep else
                  f"<p class='sub'>Last sweep {sweep['at_london']} — "
                  f"{sweep['items_seen']} releases read, {sweep['items_new']} new, "
                  f"{sweep['bodies_fetched']} full texts fetched"
                  + (f", {sweep['body_fetch_failures']} fetch failures"
                     if sweep["body_fetch_failures"] else "")
                  + (" · body-fetch budget exhausted this sweep"
                     if sweep["budget_exhausted"] else "") + ".</p>")

    # ── what happened to everything that came in ──
    totals = digest["totals"]
    by_outcome = totals["by_outcome"]
    funnel = "".join(
        f"<div class='stat'><div class='k'>{label}</div><div class='v'>{value}</div></div>"
        for label, value in [
            (f"Read in {hours}h", totals["ingested"]),
            ("Matched a company", totals["ingested"] - by_outcome.get("no_entity", 0)),
            ("Screened out", by_outcome.get("screened_out", 0)),
            ("Scored", by_outcome.get("scored", 0) + by_outcome.get("alerted", 0)),
            ("Alerted", by_outcome.get("alerted", 0)),
            ("Median detection lag",
             _secs(totals["median_detection_lag_seconds"])),
        ])

    providers_html = "".join(
        f"<tr><td>{p['provider']}</td><td>{p['ingested']}</td>"
        f"<td>{p['resolved']}</td><td>{p['scored']}</td><td>{p['alerted']}</td></tr>"
        for p in digest["by_provider"])
    providers_html = (
        "<div class='card'><div class='empty'>Nothing ingested in this window.</div></div>"
        if not providers_html else
        "<div class='card'><table><tr><th>Source</th><th>Read</th><th>Company matched</th>"
        f"<th>Scored</th><th>Alerted</th></tr>{providers_html}</table></div>")

    # ── the lead-time claim ──
    summary = lead["summary"]
    if summary["n_alerts"] == 0:
        lead_html = ("<div class='card'><div class='empty'>No alerts yet, so there "
                     "is nothing to measure. This table stays empty until an "
                     "article clears the 9.0 threshold — which is designed to be "
                     "rare.</div></div>")
    else:
        rows = "".join(
            f"<tr><td class='tick'>{a['ticker']}</td>"
            f"<td class='sub'>{a['headline'][:70]}</td>"
            f"<td>{a['score_at_alert']:.1f}</td>"
            f"<td>{_secs(a['detection_lag_seconds'])}</td>"
            f"<td>{_secs(a['alert_lag_seconds'])}</td>"
            f"<td>{_pct(a['move_before_alert_pct'])}</td>"
            f"<td>{_pct((a['move_after_alert_pct'] or {}).get('60m'))}</td>"
            f"<td>{_share(a['share_of_60m_move_still_ahead'], a['why_not_measurable'])}</td>"
            f"<td><a href='/catalysts/{a['event_id']}'>detail</a></td></tr>"
            for a in lead["alerts"])
        lead_html = (
            "<div class='card'><table>"
            "<tr><th>Ticker</th><th>Headline</th><th>Score</th>"
            "<th>Seen after</th><th>Alerted after</th>"
            "<th>Move before alert</th><th>Move after alert (60m)</th>"
            "<th>Still ahead</th><th></th></tr>"
            f"{rows}</table></div>")

    lead_stats = "".join(
        f"<div class='stat'><div class='k'>{label}</div><div class='v'>{value}</div></div>"
        for label, value in [
            ("Alerts", summary["n_alerts"]),
            ("Measurable", summary["n_measurable"]),
            ("Median time to alert", _secs(summary["median_alert_lag_seconds"])),
            ("Median share still ahead",
             "—" if summary["median_share_of_move_still_ahead"] is None
             else f"{summary['median_share_of_move_still_ahead']:.0%}"),
        ])

    delay_note = (f"<p class='sub'>{lead['delay_note']}</p>"
                  if lead["delay_note"] else "")

    return _page("News evidence", f"""
      <p class='sub'><a href='/catalysts'>← catalysts</a> ·
        <a href='/'>Earnings Sentinel</a></p>
      <h1>News → alert evidence</h1>
      <p class='sub'>Last {hours} hours · all times Europe/London ·
        <a href='/api/catalyst/ingestion'>JSON</a> ·
        <a href='/api/catalyst/lead-time'>lead-time JSON</a></p>

      <h2>Are the wires alive?</h2>
      {feeds_html}
      {sweep_html}

      <h2>What came in, and what became of it</h2>
      <div class='grid'>{funnel}</div>
      {providers_html}
      <p class='sub'>{digest['note']}</p>

      <h2>Did the alert beat the market?</h2>
      <div class='grid'>{lead_stats}</div>
      {lead_html}
      <p class='sub'>{lead['how_to_read']}</p>
      {delay_note}

      <h2>Ingest log</h2>
      {_log_table(digest['log'])}
    """)


def _log_table(log: list[dict]) -> str:
    if not log:
        return ("<div class='card'><div class='empty'>Nothing ingested in this "
                "window. If the wires above are green, the market is quiet; if "
                "they are red, that is the reason.</div></div>")
    rows = ""
    for item in log:
        marker, colour = _OUTCOME_STYLE.get(item["outcome"], ("·", "#8a929b"))
        headline = (f"<a href='{item['url']}'>{item['headline'][:110]}</a>"
                    if item["url"] else item["headline"][:110])
        target = (f"<a href='/catalysts/{item['event_id']}'>{item['outcome_label']}</a>"
                  if item["event_id"] else item["outcome_label"])
        rows += (f"<tr><td class='sub'>{item['published_london'] or '—'}</td>"
                 f"<td class='sub'>{item['source']}</td>"
                 f"<td>{headline}</td>"
                 f"<td class='tick'>{item['ticker'] or '—'}</td>"
                 f"<td>{_secs(item['detected_lag_seconds'])}</td>"
                 f"<td style='color:{colour}'>{marker} {target}</td></tr>")
    return ("<div class='card'><table>"
            "<tr><th>Published</th><th>Source</th><th>Headline</th><th>Ticker</th>"
            "<th>Seen after</th><th>Outcome</th></tr>"
            f"{rows}</table></div>")


def _secs(value) -> str:
    if value in (None, ""):
        return "—"
    value = float(value)
    if value < 90:
        return f"{value:.0f}s"
    if value < 5400:
        return f"{value / 60:.1f}m"
    return f"{value / 3600:.1f}h"


def _age(minutes) -> str:
    if minutes in (None, ""):
        return "—"
    minutes = float(minutes)
    # Wires are quiet overnight and at weekends, so an old newest-item is only
    # worth flagging once it is old enough to mean something is broken.
    colour = "#8a929b" if minutes < 240 else "#d7a63b"
    return f"<span style='color:{colour}'>{_secs(minutes * 60)} ago</span>"


def _share(value, why_not: str) -> str:
    if value is None:
        return f"<span class='sub' title='{why_not}'>pending</span>"
    colour = "#2fbf71" if value >= 0.7 else "#d7a63b" if value >= 0.3 else "#c9524b"
    return f"<span style='color:{colour}'>{value:.0%}</span>"


def _money(value) -> str:
    if value in (None, ""):
        return "—"
    value = float(value)
    for threshold, suffix in ((1e9, "bn"), (1e6, "m"), (1e3, "k")):
        if abs(value) >= threshold:
            return f"${value / threshold:,.2f}{suffix}"
    return f"${value:,.0f}"


def _num(value) -> str:
    if value in (None, ""):
        return "—"
    return f"{float(value):,.2f}"


def _ratio(value) -> str:
    if value in (None, ""):
        return "—"
    return f"{float(value):.1%}"


def _ratio_pct(value) -> str:
    if value in (None, ""):
        return "—"
    return f"{float(value):.2f}%"
