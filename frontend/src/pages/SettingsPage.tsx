import { FormEvent, useEffect, useState } from 'react';
import { Panel } from '../components/ui';
import api from '../lib/api';

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>();
  const [report, setReport] = useState({ category: 'bug', message: '' });
  const [reportMessage, setReportMessage] = useState('');
  const [saved, setSaved] = useState(false);
  useEffect(() => { api.get('/settings').then((response) => setSettings(response.data)); }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    const { id, userId, updatedAt, ...payload } = settings;
    const { data } = await api.put('/settings', payload);
    document.documentElement.dataset.theme = data.theme || 'dark';
    setSettings(data); setSaved(true);
  }
  async function sendReport(event: FormEvent) {
    event.preventDefault(); setReportMessage('');
    const { data } = await api.post('/feedback', report);
    setReportMessage(data.message);
    setReport({ category: 'bug', message: '' });
  }
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Your Setup</p><h1>Settings</h1></div></div>{settings && <Panel title="Preferences"><form className="stack" onSubmit={save}>{saved && <p className="success">Preferences saved.</p>}<label className="toggle-row"><span>Notifications</span><input type="checkbox" checked={settings.notifications} onChange={(e) => setSettings({ ...settings, notifications: e.target.checked })} /></label><label className="toggle-row"><span>Public Profile</span><input type="checkbox" checked={settings.publicProfile} onChange={(e) => setSettings({ ...settings, publicProfile: e.target.checked })} /></label><div className="form-grid"><div><label>Weekly Workout Goal</label><input type="number" min={1} max={14} value={settings.weeklyGoal} onChange={(e) => setSettings({ ...settings, weeklyGoal: +e.target.value })} /></div><div><label>Units</label><select value={settings.units} onChange={(e) => setSettings({ ...settings, units: e.target.value })}><option>metric</option><option>imperial</option></select></div><div><label>Theme</label><select value={settings.theme} onChange={(e) => setSettings({ ...settings, theme: e.target.value })}><option>dark</option><option>light</option></select></div></div><button>Save Settings</button></form></Panel>}<Panel title="Report A Bug Or Idea"><form className="stack" onSubmit={sendReport}>{reportMessage && <p className="success">{reportMessage}</p>}<div><label>Category</label><select value={report.category} onChange={(event) => setReport({ ...report, category: event.target.value })}><option value="bug">Bug</option><option value="idea">Idea</option><option value="account">Account</option><option value="other">Other</option></select></div><div><label>Message</label><textarea required minLength={5} value={report.message} onChange={(event) => setReport({ ...report, message: event.target.value })} placeholder="What happened, what page were you on, and what did you expect?" /></div><button>Send Report</button></form></Panel></div>;
}
