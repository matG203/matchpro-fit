mport { useEffect, useState } from ''react'';
import { Settings, User, Bell, Shield, Trash2, ChevronRight, LogOut } from ''lucide-react'';
import { useNavigate } from ''react-router-dom'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

interface UserSettings {
  notificationsEnabled: boolean;
  emailNotifications: boolean;
  privacyPublic: boolean;
  maxWorkoutDuration: number;
  preferredWorkoutTime: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    api.get(''/settings'').then(r => setSettings(r.data.settings || {
      notificationsEnabled: true, emailNotifications: false,
      privacyPublic: false, maxWorkoutDuration: 60, preferredWorkoutTime: ''morning'',
    }));
  }, []);

  const save = async () => {
    setSaving(true);
    await api.put(''/settings'', settings);
    setSaved(true); setSaving(false);
    setTimeout(() => setSaved(false), 2000);
  };

  const deleteAccount = async () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setDeleting(true);
    await api.delete(''/auth/account'');
    logout();
    navigate(''/'');
  };

  const update = (key: keyof UserSettings, val: boolean | number | string) => {
    setSettings(s => s ? { ...s, [key]: val } : s);
    setSaved(false);
  };

  if (!settings) return <div className="flex items-center justify-center min-h-screen"><div className="text-electric-400 animate-pulse font-display font-bold">LOADING...</div></div>;

  return (
    <div className="px-4 py-4 space-y-5 pb-10">
      <div className="flex items-center gap-3">
        <Settings size={24} className="text-electric-400" />
        <h1 className="section-title">Settings</h1>
      </div>

      {/* Account info */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><User size={14} /> Account</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center py-2">
            <span className="text-gray-400 text-sm">Username</span>
            <span className="text-white font-medium text-sm">@{user?.username}</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-gray-400 text-sm">Friend Code</span>
            <code className="text-electric-400 text-xs font-mono">{user?.friendCode?.slice(0, 12)}...</code>
          </div>
          <button onClick={() => navigate(''/onboarding'')} className="w-full flex items-center justify-between py-2 text-sm text-gray-400 hover:text-white transition-colors">
            <span>Edit Profile & Goals</span>
            <ChevronRight size={16} />
          </button>
          <button onClick={() => navigate(''/wearables'')} className="w-full flex items-center justify-between py-2 text-sm text-gray-400 hover:text-white transition-colors">
            <span>Manage Wearables</span>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Notifications */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Bell size={14} /> Notifications</h3>
        <div className="space-y-3">
          {[
            { key: ''notificationsEnabled'', label: ''In-app notifications'' },
            { key: ''emailNotifications'', label: ''Email notifications'' },
          ].map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-gray-300">{label}</span>
              <button
                onClick={() => update(key as keyof UserSettings, !settings[key as keyof UserSettings])}
                className={`w-12 h-6 rounded-full transition-colors ${settings[key as keyof UserSettings] ? ''bg-electric-500'' : ''bg-pitch-600''}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white mt-0.5 transition-transform ${settings[key as keyof UserSettings] ? ''translate-x-6.5'' : ''translate-x-0.5''} mx-0.5`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Workout prefs */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Settings size={14} /> Workout Preferences</h3>
        <div className="space-y-4">
          <div>
            <label className="label mb-2 block">Max Workout Duration: {settings.maxWorkoutDuration} mins</label>
            <input type="range" min={10} max={120} step={5} value={settings.maxWorkoutDuration} onChange={e => update(''maxWorkoutDuration'', Number(e.target.value))} className="w-full accent-electric-500" />
          </div>
          <div>
            <label className="label mb-2 block">Preferred Workout Time</label>
            <div className="flex gap-2 flex-wrap">
              {[''morning'', ''lunchtime'', ''afternoon'', ''evening''].map(t => (
                <button key={t} onClick={() => update(''preferredWorkoutTime'', t)} className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${settings.preferredWorkoutTime === t ? ''bg-electric-500/20 border-electric-500 text-electric-400'' : ''bg-pitch-700 border-pitch-600 text-gray-400''}`}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Privacy */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Shield size={14} /> Privacy</h3>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-300">Public Profile</div>
            <div className="text-xs text-gray-600">Allow non-friends to see your card</div>
          </div>
          <button
            onClick={() => update(''privacyPublic'', !settings.privacyPublic)}
            className={`w-12 h-6 rounded-full transition-colors ${settings.privacyPublic ? ''bg-electric-500'' : ''bg-pitch-600''}`}
          >
            <div className={`w-5 h-5 rounded-full bg-white mt-0.5 transition-transform ${settings.privacyPublic ? ''translate-x-6'' : ''translate-x-0.5''} mx-0.5`} />
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-3">
          Health data is stored securely and never sold to third parties. You can delete your account and all data at any time.
        </p>
      </div>

      {/* Save button */}
      <button onClick={save} disabled={saving} className={`w-full py-3 font-display font-bold uppercase tracking-wide text-base rounded-lg transition-all ${saved ? ''bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'' : ''btn-primary''}`}>
        {saving ? ''Saving...'' : saved ? ''Saved!'' : ''Save Settings''}
      </button>

      {/* Sign out */}
      <button onClick={() => { logout(); navigate(''/''); }} className="w-full flex items-center justify-center gap-2 py-3 rounded-lg border border-pitch-600 text-gray-400 hover:text-white hover:border-gray-500 transition-colors text-sm font-medium">
        <LogOut size={16} /> Sign Out
      </button>

      {/* Delete account */}
      <div className="card border-red-500/20">
        <h3 className="label mb-2 text-red-400 flex items-center gap-2"><Trash2 size={14} /> Danger Zone</h3>
        <p className="text-xs text-gray-500 mb-3">Permanently delete your account and all data. This cannot be undone.</p>
        <button
          onClick={deleteAccount}
          disabled={deleting}
          className={`w-full py-2.5 rounded-lg border text-sm font-semibold transition-all ${
            confirmDelete
              ? ''bg-red-500 border-red-500 text-white''
              : ''border-red-500/40 text-red-400 hover:bg-red-500/10''
          }`}
        >
          {deleting ? ''Deleting...'' : confirmDelete ? ''âš ï¸ Confirm â€” Delete Everything'' : ''Delete Account''}
        </button>
        {confirmDelete && <p className="text-xs text-red-400 mt-2 text-center">Tap again to permanently delete</p>}
      </div>
    </div>
  );
}
