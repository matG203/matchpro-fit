mport { useState } from ''react'';
import { useNavigate, Link } from ''react-router-dom'';
import { useAuthStore } from ''../store/authStore'';
import { Eye, EyeOff, Zap } from ''lucide-react'';

export default function RegisterPage() {
  const [email, setEmail] = useState('''');
  const [username, setUsername] = useState('''');
  const [password, setPassword] = useState('''');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('''');
  const [loading, setLoading] = useState(false);
  const { register } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('''');
    if (password.length < 8) { setError(''Password must be at least 8 characters''); return; }
    setLoading(true);
    try {
      await register(email, username, password);
      navigate(''/onboarding'');
    } catch (err: any) {
      setError(err.response?.data?.error || ''Registration failed'');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col justify-center px-6 py-12">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-xl bg-electric-500/20 border border-electric-500/30 flex items-center justify-center">
            <Zap size={20} className="text-electric-400" />
          </div>
        </div>
        <h1 className="font-display font-black text-4xl text-white tracking-wide">
          CREATE ACCOUNT
        </h1>
        <p className="text-gray-400 mt-2 text-sm">Start your MatchFit Pro journey</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}
        <div>
          <label className="label mb-1.5 block">Email</label>
          <input type="email" className="input-field" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label mb-1.5 block">Username</label>
          <input type="text" className="input-field" placeholder="coolplayer99" value={username} onChange={e => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''''))} required minLength={3} maxLength={30} />
          <p className="text-xs text-gray-600 mt-1">Letters, numbers, underscores only</p>
        </div>
        <div>
          <label className="label mb-1.5 block">Password</label>
          <div className="relative">
            <input type={showPass ? ''text'' : ''password''} className="input-field pr-10" placeholder="Min 8 characters" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
            <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full py-3 font-display font-bold uppercase tracking-wide text-base mt-2 disabled:opacity-50">
          {loading ? ''Creating Account...'' : ''Create Account''}
        </button>
      </form>

      <p className="text-xs text-gray-600 text-center mt-4 px-4">
        By signing up you agree to our terms. Health data is stored securely and never sold.
      </p>

      <div className="mt-4 text-center">
        <p className="text-gray-500 text-sm">
          Already have an account?{'' ''}
          <Link to="/login" className="text-electric-400 hover:text-electric-300 font-medium">Sign In</Link>
        </p>
      </div>
    </div>
  );
}
