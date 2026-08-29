"""Server-rendered dashboard (MVP). Consumes the same data as /api."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.routes import release_detail, results_view, today_view

router = APIRouter()

_STYLE = """
:root { color-scheme: light dark; --bg:#0f1216; --fg:#e8eaed; --muted:#9aa3ad;
        --line:#252b33; --card:#161a20; --accent:#4da3ff; }
@media (prefers-color-scheme: light) {
  :root { --bg:#f7f8fa; --fg:#12161c; --muted:#5b6572; --line:#e2e6eb;
          --card:#ffffff; --accent:#0b62d0; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 -apple-system,
       BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1000px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 20px; letter-spacing:-.01em; margin:0 0 4px; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing:.06em;
     color: var(--muted); margin: 32px 0 10px; }
.sub { color: var(--muted); margin: 0 0 8px; }
.card { background: var(--card); border:1px solid var(--line); border-radius:10px;
        overflow:hidden; }
table { width:100%; border-collapse: collapse; }
th { text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.06em;
     color:var(--muted); padding:10px 12px; border-bottom:1px solid var(--line); }
td { padding:10px 12px; border-bottom:1px solid var(--line); }
tr:last-child td { border-bottom:none; }
a { color: var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.tick { font-weight:600; }
.score { font-variant-numeric: tabular-nums; font-weight:600; }
.pill { display:inline-block; padding:1px 8px; border-radius:999px; font-size:11px;
        border:1px solid var(--line); color:var(--muted); }
.pos { color:#2fbf71; } .neg { color:#f2564b; }
.empty { padding:20px 12px; color:var(--muted); }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; }
.stat .k { color:var(--muted); font-size:11px; text-transform:uppercase;
           letter-spacing:.06em; }
.stat .v { font-size:20px; font-weight:600; font-variant-numeric:tabular-nums; }
ul { margin:6px 0; padding-left:18px; }
"""


def _emoji(score: float) -> str:
    if score >= 9.0:
        return "🔥"
    if score >= 8.0:
        return "🟢"
    if score >= 7.0:
        return "🟡"
    return "🔴"


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{_STYLE}</style></head>"
        f"<body><main>{body}</main></body></html>")


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    cls = "pos" if value >= 0 else "neg"
    return f"<span class='{cls}'>{value:+.1f}%</span>"


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    today = today_view()
    results = results_view(limit=25)

    if today["events"]:
        rows = "".join(
            f"<tr><td>{e['expected_time_london']}</td>"
            f"<td class='tick'>{e['ticker']}</td>"
            f"<td>{e['company'] or ''}</td>"
            f"<td><span class='pill' title=\"{e['confidence_reason']}\">"
            f"{e['confidence']}</span></td>"
            f"<td><span class='pill'>{e['status']}</span></td></tr>"
            for e in today["events"])
        next_table = (
            "<div class='card'><table><tr><th>Time (London)</th><th>Ticker</th>"
            "<th>Company</th><th>Confidence</th><th>Status</th></tr>"
            f"{rows}</table></div>")
    else:
        next_table = ("<div class='card'><div class='empty'>No earnings on the "
                      "watchlist. Run discovery to populate it.</div></div>")

    if results["results"]:
        rows = "".join(
            f"<tr><td class='tick'>{r['ticker']}</td>"
            f"<td>{r['release_time_london'] or '—'}</td>"
            f"<td class='score'>{_emoji(r['final_trade_score'])} "
            f"{r['final_trade_score']:.1f}</td>"
            f"<td>{_pct(r['reaction_pct'])}</td>"
            f"<td>{r['confidence']:.0f}%</td>"
            f"<td><a href='/releases/{r['release_id']}'>detail</a></td></tr>"
            for r in results["results"])
        results_table = (
            "<div class='card'><table><tr><th>Ticker</th><th>Release</th><th>Score</th>"
            f"<th>Reaction</th><th>Confidence</th><th></th></tr>{rows}</table></div>")
    else:
        results_table = ("<div class='card'><div class='empty'>No scored releases "
                         "yet.</div></div>")

    return _page("Earnings Radar", f"""
      <h1>Earnings Radar</h1>
      <p class='sub'>Sentinel · <a href='/catalysts'>Catalyst Sentinel →</a></p>
      <p class='sub'>All times Europe/London · <a href='/api/health'>system health</a>
       · <a href='/api/audit'>audit log</a></p>
      <h2>Next earnings</h2>{next_table}
      <h2>Results</h2>{results_table}
    """)


@router.get("/releases/{release_id}", response_class=HTMLResponse)
def release_page(release_id: int) -> HTMLResponse:
    data = release_detail(release_id)
    scores = data["scores"] or {}
    market = data["market"] or {}
    analysis = data["analysis"] or {}

    stats = "".join(
        f"<div class='stat'><div class='k'>{label}</div>"
        f"<div class='v'>{value}</div></div>"
        for label, value in [
            ("Final trade score",
             f"{scores.get('final_trade_score', 0):.1f}" if scores else "—"),
            ("Earnings quality",
             f"{scores.get('earnings_quality', 0):.1f}" if scores else "—"),
            ("Market confirmation",
             f"{scores.get('market_confirmation', 0):.1f}" if scores else "—"),
            ("Current entry", f"{scores.get('entry_score', 0):.1f}" if scores else "—"),
            ("Confidence",
             f"{scores.get('analysis_confidence', 0):.0f}%" if scores else "—"),
            ("Detection latency",
             f"{data['release']['detection_latency_ms']} ms"
             if data["release"]["detection_latency_ms"] is not None else "—"),
        ])

    financials = "".join(
        f"<tr><td>{f['metric']}</td><td>{f['value']:,.4g}</td><td>{f['unit']}</td>"
        f"<td>{f['confidence']:.2f}</td></tr>" for f in data["financials"])
    financials_table = (f"<div class='card'><table><tr><th>Metric</th><th>Value</th>"
                        f"<th>Unit</th><th>Conf.</th></tr>{financials}</table></div>"
                        if financials else
                        "<div class='card'><div class='empty'>No metrics extracted.</div></div>")

    def bullets(items: list[str] | None, empty: str) -> str:
        if not items:
            return f"<p class='sub'>{empty}</p>"
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"

    sources = "".join(f"<li><a href='{s['url']}'>{s['source']}</a></li>"
                      for s in data["release"]["sources"])

    return _page(f"{data['ticker']} — Earnings Radar", f"""
      <p class='sub'><a href='/'>← dashboard</a></p>
      <h1>{data['ticker']} · {data['company']} · {data['fiscal']}</h1>
      <p class='sub'>Published {data['release']['published_at_london'] or 'unknown'} ·
        {data['release']['document_type'] or 'document'} ·
        verified: {data['release']['verified']}</p>
      <div class='grid'>{stats}</div>

      <h2>Vetoes applied</h2>
      {bullets(scores.get('vetoes'), 'None — no capping rule triggered.')}

      <h2>Market</h2>
      <div class='card'><table>
        <tr><th>Prev close</th><th>Pre-release</th><th>Reaction</th>
            <th>vs prev close</th><th>1m run</th><th>Pattern</th></tr>
        <tr><td>{market.get('prev_close') or '—'}</td>
            <td>{market.get('pre_release_price') or '—'}</td>
            <td>{_pct(market.get('current_reaction_pct'))}</td>
            <td>{_pct(market.get('reaction_vs_prev_close_pct'))}</td>
            <td>{_pct(market.get('run_1m_pct'))}</td>
            <td>{market.get('reaction_pattern', '—')}</td></tr>
      </table></div>

      <h2>Extracted financials</h2>{financials_table}

      <h2>Bull case</h2><p>{analysis.get('bull_case') or '—'}</p>
      <h2>Bear case</h2><p>{analysis.get('bear_case') or '—'}</p>
      <h2>Hidden negatives</h2>{bullets(analysis.get('hidden_negatives'), '—')}
      <h2>Previously known</h2>{bullets(analysis.get('pre_announced'), '—')}
      <h2>One-off items</h2>{bullets(analysis.get('one_off_items'), '—')}
      <h2>Reasoning summary</h2><p>{analysis.get('reasoning_summary') or '—'}</p>

      <h2>Sources</h2><div class='card'><ul>{sources or '<li>—</li>'}</ul></div>
      <p class='sub'><a href='/api/audit?release_id={release_id}'>audit trail for this
        release</a></p>
    """)
