"""Did the delayed feed actually cost anything?

The Starter plan is a deliberate bet: pay $29 to validate the system, and
upgrade to real-time only if the delay demonstrably loses you something. That
decision deserves evidence rather than a hunch, so every re-score records what
changed when the data arrived, and this reports it.

The question is not "did the score move" — a score that drifts 8.1 → 8.3 costs
nothing. It is: **how often did waiting 15 minutes change what you would have
done?** Two things count:

  * A catalyst that was still available at detection but had already run by the
    time the data arrived. A real-time feed would have caught it in time.
  * A catalyst held below the push threshold on arrival that cleared it once
    priced. The alert was late by the length of the delay.

Everything is reported against a plainly stated sample size. With eleven
events this is an anecdote, and it says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.catalyst_models import CatalystEvent, CatalystScore, ReactionAnalysis

# A score change smaller than this is noise, not a different decision.
MATERIAL_SCORE_CHANGE = 0.5


@dataclass
class DelayImpact:
    delay_minutes: float = 0.0
    scored: int = 0
    scored_blind: int = 0            # first score made before the move was visible
    rescored: int = 0
    still_waiting: int = 0

    would_have_alerted_sooner: int = 0
    move_already_gone: int = 0
    material_changes: int = 0

    mean_abs_change: float | None = None
    examples: list[dict] = field(default_factory=list)
    verdict: str = ""

    def as_dict(self) -> dict:
        return {
            "delay_minutes": self.delay_minutes,
            "sample": {
                "scored": self.scored,
                "scored_before_move_visible": self.scored_blind,
                "rescored": self.rescored,
                "still_waiting": self.still_waiting,
            },
            "impact": {
                "would_have_alerted_sooner": self.would_have_alerted_sooner,
                "move_already_gone_by_the_time_we_saw_it": self.move_already_gone,
                "material_score_changes": self.material_changes,
                "mean_absolute_score_change": self.mean_abs_change,
            },
            "examples": self.examples,
            "verdict": self.verdict,
        }


def assess_delay_impact(session: Session, settings: Settings,
                        limit: int = 200) -> DelayImpact:
    delay = max(0.0, float(settings.market_data_delay_seconds))
    impact = DelayImpact(delay_minutes=round(delay / 60, 1))

    impact.scored = session.query(CatalystScore).filter_by(revision=1).count()
    if delay <= 0:
        impact.verdict = ("Real-time feed — nothing is scored blind, so there is "
                          "no delay to measure.")
        return impact

    reactions = (session.query(ReactionAnalysis)
                 .filter(ReactionAnalysis.data_delay_seconds > 0)
                 .filter(ReactionAnalysis.move_observable.is_(False)
                         | ReactionAnalysis.rescored_at_utc.isnot(None))
                 .limit(limit).all())
    impact.scored_blind = len(reactions)

    changes: list[float] = []
    for reaction in reactions:
        if reaction.rescored_at_utc is None:
            impact.still_waiting += 1
            continue
        impact.rescored += 1

        revisions = (session.query(CatalystScore)
                     .filter_by(event_id=reaction.event_id)
                     .order_by(CatalystScore.revision.asc()).all())
        if len(revisions) < 2:
            continue

        first, last = revisions[0], revisions[-1]
        change = last.upside_catalyst_score - first.upside_catalyst_score
        changes.append(abs(change))
        if abs(change) >= MATERIAL_SCORE_CHANGE:
            impact.material_changes += 1

        threshold = settings.catalyst_push_score
        crossed_up = (first.upside_catalyst_score < threshold
                      <= last.upside_catalyst_score)
        if crossed_up:
            impact.would_have_alerted_sooner += 1

        # Reaction Room collapsing on arrival means the move was gone before we
        # could see it — the case a real-time feed would actually have caught.
        if last.reaction_room <= 3.0 and first.reaction_room > 3.0:
            impact.move_already_gone += 1

        if abs(change) >= MATERIAL_SCORE_CHANGE and len(impact.examples) < 10:
            event = session.get(CatalystEvent, reaction.event_id)
            impact.examples.append({
                "ticker": event.ticker if event else "",
                "event_type": event.event_type if event else "",
                "score_on_detection": round(first.upside_catalyst_score, 2),
                "score_once_priced": round(last.upside_catalyst_score, 2),
                "change": round(change, 2),
                "reaction_room_once_priced": round(last.reaction_room, 2),
                "crossed_push_threshold": crossed_up,
            })

    if changes:
        impact.mean_abs_change = round(sum(changes) / len(changes), 2)

    impact.verdict = _verdict(impact)
    return impact


def _verdict(impact: DelayImpact) -> str:
    """A plain-English read, honest about how little the sample may prove."""
    if impact.rescored == 0:
        return ("No catalyst has been re-scored yet, so there is nothing to judge. "
                "Leave it running through some real events first.")

    if impact.rescored < 10:
        return (f"Only {impact.rescored} re-scored catalyst"
                f"{'s' if impact.rescored != 1 else ''} so far — too few to draw a "
                "conclusion. This is an anecdote, not evidence.")

    costly = impact.would_have_alerted_sooner + impact.move_already_gone
    rate = costly / impact.rescored

    if rate >= 0.3:
        return (f"The delay cost you something in {costly} of {impact.rescored} cases "
                f"({rate:.0%}) — either the alert was late or the move had gone by the "
                "time it was visible. That is a real case for the real-time plan.")
    if rate >= 0.1:
        return (f"The delay mattered in {costly} of {impact.rescored} cases ({rate:.0%}). "
                "Worth weighing against the cost, but not obviously decisive.")
    return (f"The delay changed the decision in only {costly} of {impact.rescored} cases "
            f"({rate:.0%}). On this evidence the real-time plan would not have bought "
            "you much.")
