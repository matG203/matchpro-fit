import { useEffect, useState } from 'react';
import { UserPlus, Users, Check, X, Trash2, Copy } from 'lucide-react';
import api from '../lib/api';
import { useAuthStore } from '../store/authStore';

interface Friend { id: string; userId: string; username: string; displayName: string; overall: number; tier: string; friendCode: string; }
interface FriendRequest { id: string; sender: { username: string; profile?: { displayName: string } } }

export default function FriendsPage() {
  const [friends, setFriends] = useState<Friend[]>([]);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState('');
  const { user } = useAuthStore();

  const load = async () => {
    const [f, r] = await Promise.all([api.get('/friends'), api.get('/friends/requests')]);
    setFriends(f.data); setRequests(r.data); setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const sendRequest = async () => {
    if (!search.trim()) return;
    setAdding(true); setMsg('');
    try {
      await api.post('/friends/request', { usernameOrCode: search.trim() });
      setMsg('Friend request sent!'); setSearch('');
    } catch (err: any) { setMsg(err.response?.data?.error || 'Error'); }
    finally { setAdding(false); }
  };

  const accept = async (id: string) => { await api.post('/friends/accept', { requestId: id }); load(); };
  const decline = async (id: string) => { await api.post('/friends/decline', { requestId: id }); load(); };
  const remove = async (id: string) => { await api.delete(`/friends/${id}`); load(); };

  const TIER_COLORS: Record<string, string> = { bronze: '#cd7f32', silver: '#94a3b8', common_gold: '#f59e0b', rare_gold: '#fbbf24', elite: '#a78bfa' };

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center gap-3">
        <Users size={24} className="text-electric-400" />
        <h1 className="section-title">Friends</h1>
      </div>

      {/* Your friend code */}
      <div className="card bg-electric-500/5 border-electric-500/20">
        <div className="text-xs text-gray-400 mb-1">Your Friend Code</div>
        <div className="flex items-center gap-2">
          <code className="flex-1 font-mono text-electric-400 text-sm bg-pitch-800 px-3 py-2 rounded-lg truncate">{user?.friendCode}</code>
          <button onClick={() => navigator.clipboard.writeText(user?.friendCode || '')} className="btn-secondary p-2"><Copy size={14} /></button>
        </div>
        <p className="text-xs text-gray-600 mt-1">Share this with friends to connect</p>
      </div>

      {/* Add friend */}
      <div className="card">
        <h3 className="label mb-3">Add Friend</h3>
        {msg && <div className={`mb-3 text-sm px-3 py-2 rounded-lg ${msg.includes('sent') ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>{msg}</div>}
        <div className="flex gap-2">
          <input className="input-field flex-1" placeholder="Username or friend code" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendRequest()} />
          <button onClick={sendRequest} disabled={adding} className="btn-primary px-4"><UserPlus size={18} /></button>
        </div>
      </div>

      {/* Pending requests */}
      {requests.length > 0 && (
        <div className="card">
          <h3 className="label mb-3">Pending Requests ({requests.length})</h3>
          <div className="space-y-2">
            {requests.map(r => (
              <div key={r.id} className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="text-white font-medium text-sm">{r.sender.profile?.displayName || r.sender.username}</div>
                  <div className="text-xs text-gray-500">@{r.sender.username}</div>
                </div>
                <button onClick={() => accept(r.id)} className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"><Check size={16} /></button>
                <button onClick={() => decline(r.id)} className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30"><X size={16} /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Friends list */}
      <div>
        <h3 className="label mb-3">Friends ({friends.length})</h3>
        {loading ? <div className="text-gray-500 text-sm text-center py-4">Loading...</div>
          : friends.length === 0 ? <div className="card text-center py-6 text-gray-500 text-sm">No friends yet â€” add someone!</div>
          : (
            <div className="space-y-2">
              {friends.map(f => (
                <div key={f.id} className="card flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center font-display font-black text-lg" style={{ backgroundColor: (TIER_COLORS[f.tier] || '#cd7f32') + '20', color: TIER_COLORS[f.tier] || '#cd7f32', border: `2px solid ${TIER_COLORS[f.tier] || '#cd7f32'}40` }}>
                    {f.overall}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-semibold text-sm">{f.displayName}</div>
                    <div className="text-xs text-gray-500">@{f.username}</div>
                  </div>
                  <button onClick={() => remove(f.userId)} className="p-2 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-400/10 transition-colors"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}
