mport { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { Eye, EyeOff, Zap } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col justify-center px-6">
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-xl bg-electric-500/20 border border-electric-500/30 flex items-center justify-center">
            <Zap size={20} className="text-electric-400" />
          </div>
        </div>
        <h1 className="font-display font-black text-4xl text-white tracking-wide">
          MATCH<span className="text-electric-400">FIT</span> PRO
        </h1>
        <p className="text-gray-400 mt-2 text-sm">Sign in to your account</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}
        <div>
          <label className="label mb-1.5 block">Email</label>
          <input
            type="email"
            className="input-field"
            placeholder="you@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label mb-1.5 block">Password</label>
          <div className="relative">
            <input
              type={showPass ? 'text' : 'password'}
              className="input-field pr-10"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full py-3 font-display font-bold uppercase tracking-wide text-base mt-2 disabled:opacity-50">
          {loading ? 'Signing In...' : 'Sign In'}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-gray-500 text-sm">
          Don't have an account?{' '}
          <Link to="/register" className="text-electric-400 hover:text-electric-300 font-medium">
            Sign Up
          </Link>
        </p>
      </div>

      <div className="mt-4 text-center">
        <p className="text-gray-600 text-xs">Demo: demo@matchfitpro.com / matchfit123</p>
      </div>
    </div>
  );
}
