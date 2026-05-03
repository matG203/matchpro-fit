import { useNavigate } from ''react-router-dom'';
import { Zap, Trophy, Users, Activity, Shield, Star } from ''lucide-react'';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col">
      {/* Hero */}
      <div className="relative overflow-hidden px-6 pt-16 pb-12 flex-1 flex flex-col justify-center">
        <div className="absolute inset-0 bg-gradient-to-br from-electric-600/10 via-transparent to-purple-600/10" />
        <div className="relative text-center">
          <div className="inline-block mb-4 px-3 py-1 bg-electric-500/10 border border-electric-500/30 rounded-full text-electric-400 text-xs font-medium uppercase tracking-wider">
            Football Fitness Gamification
          </div>
          <h1 className="font-display font-black text-6xl tracking-tight text-white mb-2">
            MATCH<span className="text-electric-400">FIT</span>
          </h1>
          <h2 className="font-display font-bold text-3xl text-gray-300 mb-6 tracking-wide">PRO</h2>
          <p className="text-gray-400 max-w-xs mx-auto mb-8 leading-relaxed">
            Level up your football fitness. Track readiness, earn XP, upgrade your player card, and compete with friends.
          </p>
          <div className="flex flex-col gap-3">
            <button onClick={() => navigate(''/register'')} className="btn-primary w-full text-lg py-3 font-display font-bold uppercase tracking-wide">
              Get Started Free
            </button>
            <button onClick={() => navigate(''/login'')} className="btn-secondary w-full">
              Sign In
            </button>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="px-6 pb-12 space-y-4">
        {[
          { icon: Activity, title: ''Match Readiness %'', desc: ''Track exactly how ready you are for your next match or fitness goal'' },
          { icon: Star, title: ''Player Card'', desc: ''Earn XP and upgrade your football-style card from Bronze to Elite'' },
          { icon: Zap, title: ''XP & Challenges'', desc: ''Daily and weekly challenges to keep you grinding and improving'' },
          { icon: Trophy, title: ''Leaderboards'', desc: ''Compete with friends on XP, steps, workouts, and overall rating'' },
          { icon: Shield, title: ''Smart Workouts'', desc: ''AI-generated sessions adapted to your energy level and equipment'' },
          { icon: Users, title: ''Friends & Social'', desc: ''Add friends, compare player cards, and race up the leaderboard'' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="flex items-start gap-4 card">
            <div className="w-10 h-10 rounded-xl bg-electric-500/10 border border-electric-500/20 flex items-center justify-center flex-shrink-0">
              <Icon size={20} className="text-electric-400" />
            </div>
            <div>
              <div className="font-semibold text-white text-sm mb-0.5">{title}</div>
              <div className="text-gray-400 text-xs leading-relaxed">{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
