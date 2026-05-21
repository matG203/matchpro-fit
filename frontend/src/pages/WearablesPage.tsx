import { FormEvent, useEffect, useState } from 'react';
import { Panel } from '../components/ui';
import api from '../lib/api';

export default function WearablesPage() {
  const [device, setDevice] = useState<any>({ deviceType: 'watch', deviceName: 'MatchFit Sync', connected: false, dailySteps: 0, heartRate: 0, sleepHours: 0 });
  useEffect(() => { api.get('/wearables').then((response) => setDevice((current: any) => ({ ...current, ...response.data }))); }, []);
  async function save(event: FormEvent) { event.preventDefault(); const { data } = await api.put('/wearables', device); setDevice(data); }
  return <div className="page"><h1>Wearables</h1><div className="grid-2"><Panel title="Simulated Device"><form className="stack" onSubmit={save}><div className="form-grid"><div><label>Device type</label><input value={device.deviceType || ''} onChange={(e) => setDevice({ ...device, deviceType: e.target.value })} /></div><div><label>Device name</label><input value={device.deviceName || ''} onChange={(e) => setDevice({ ...device, deviceName: e.target.value })} /></div></div><label className="inline"><input style={{ width: 'auto' }} type="checkbox" checked={device.connected} onChange={(e) => setDevice({ ...device, connected: e.target.checked })} /> Connected</label><button>Sync device</button></form></Panel><Panel title="Latest Sync"><div className="stat-grid">{[['Steps', 'dailySteps'], ['Heart rate', 'heartRate'], ['Sleep', 'sleepHours']].map(([label, key]) => <div className="stat" key={key}><strong>{device[key] || 0}</strong><small>{label}</small></div>)}</div><div className="form-grid" style={{ marginTop: '1rem' }}>{['dailySteps', 'heartRate', 'sleepHours'].map((key) => <div key={key}><label>{key}</label><input type="number" value={device[key] || 0} onChange={(e) => setDevice({ ...device, [key]: +e.target.value })} /></div>)}</div></Panel></div></div>;
}
