import { ArrowRight, Dumbbell, Flame, Trophy } from 'lucide-react';
import { Link } from 'react-router-dom';
import PlayerCard from '../components/card/PlayerCard';

export default function LandingPage() {
  return (
    <main className="landing">
      <div className="landing-grid">
        <section className="landing-copy">
          <span className="eyebrow">Football fitness, levelled up</span>
          <h1>MatchFit Pro</h1>
          <p>Track the work behind your football, turn training into XP, build a player card, and chase the next tier with your mates.</p>
          <div className="actions"><Link className="button" to="/register">Create account <ArrowRight size={18} /></Link><Link className="button secondary" to="/login">Sign in</Link></div>
          <div className="stat-grid" style={{ marginTop: '1.3rem' }}>
            <div className="stat"><Flame size={18} /><strong>XP</strong><small>Workouts and recovery logs</small></div>
            <div className="stat"><Trophy size={18} /><strong>Tiers</strong><small>Bronze to Elite</small></div>
            <div className="stat"><Dumbbell size={18} /><strong>Ready</strong><small>Match readiness scoring</small></div>
          </div>
        </section>
        <aside className="pitch-visual">
          <p className="muted">Form rising this week</p>
          <div className="mini-card"><PlayerCard card={{ overall: 84, pace: 86, shooting: 79, passing: 88, dribbling: 85, defending: 72, physical: 83, user: { username: 'matchfit', tier: 'Gold', avatarId: 'captain', position: 'CM' } }} /></div>
        </aside>
      </div>
    </main>
  );
}
