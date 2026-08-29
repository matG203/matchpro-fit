"""Catalyst dashboard pages (spec §99-101)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.catalyst_routes import event_detail, live_catalysts
from app.api.dashboard import _page, _pct

router = APIRouter()


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
                 "see <a href='/api/catalyst/news'>ingest log</a>.</div></div>")
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
        <a href='/api/catalyst/performance'>calibration</a> ·
        <a href='/api/catalyst/news'>ingest log</a></p>
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
