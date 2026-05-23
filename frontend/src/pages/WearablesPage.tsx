import { FormEvent, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

export default function WearablesPage() {
  const [device, setDevice] = useState<any>({ deviceType: 'watch', deviceName: 'MatchFit Sync', connected: false, dailySteps: 8000, heartRate: 62, sleepHours: 7.5 });
  const [googleHealthReady, setGoogleHealthReady] = useState(false);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [search, setSearch] = useSearchParams();
  const load = () => api.get('/wearables').then(({ data }) => { setDevice((current: any) => ({ ...current, ...data.device })); setGoogleHealthReady(data.googleHealthReady); });
  useEffect(() => { load(); if (search.get('googleHealth') === 'connected') { setMessage('Google Health connected. Press Sync Google Health to pull today\'s tracker data.'); setSearch({}, { replace: true }); } }, []);
  async function save(event: FormEvent) { event.preventDefault(); setBusy('demo'); try { const { data } = await api.put('/wearables', device); setDevice(data.device); setMessage(data.readiness ? `Demo sync logged to Health. Readiness is ${data.readiness.score}%.` : 'Demo device saved.'); } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(''); } }
  function connect() { setDevice((current: any) => ({ ...current, connected: true })); setMessage('Device ready. Press Sync device to send its numbers into Health.'); }
  async function connectGoogleHealth() {
    setBusy('google');
    try { const { data } = await api.get('/wearables/google-health/connect'); location.assign(data.url); }
    catch (error) { setMessage(errorMessage(error)); setBusy(''); }
  }
  async function syncGoogleHealth() {
    setBusy('sync');
    try { const { data } = await api.post('/wearables/google-health/sync'); setDevice(data.device); setMessage(`Google Health synced. Readiness is ${data.readiness.score}%.`); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(''); }
  }
  async function disconnectGoogleHealth() {
    setBusy('disconnect');
    try { const { data } = await api.delete('/wearables/google-health'); setDevice(data.device); setMessage('Google Health disconnected.'); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(''); }
  }
  const googleConnected = device.provider === 'google-health' && device.connected;
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Wearable data</p><h1>Wearables</h1></div><span className={`connection-pill ${googleConnected ? 'online' : ''}`}>{googleConnected ? 'Google Health connected' : 'No real wearable'}</span></div>{message && <p className={message.match(/failed|not|error/i) ? 'error' : 'success'}>{message}</p>}<Panel title="Google Health Connection"><p className="muted">Connect Google Health to import wearable tracker data such as today&apos;s steps, sleep, and heart rate into MatchFit Health, readiness, objectives, and XP.</p><div className="actions">{googleConnected ? <><button disabled={Boolean(busy)} onClick={syncGoogleHealth}>{busy === 'sync' ? 'Syncing...' : 'Sync Google Health'}</button><button className="secondary" disabled={Boolean(busy)} onClick={disconnectGoogleHealth}>Disconnect</button></> : <button disabled={!googleHealthReady || Boolean(busy)} onClick={connectGoogleHealth}>{googleHealthReady ? busy === 'google' ? 'Opening Google...' : 'Connect Google Health' : 'Google Health setup needed'}</button>}</div>{!googleHealthReady && <p className="muted" style={{ marginTop: '1rem' }}>Google Health client id and secret must be added to Railway before live Google sign-in can open.</p>}</Panel><div className="grid-2"><Panel title="Demo Sync Fallback"><p className="muted">Use this while testing without Google Health connected.</p><form className="stack" onSubmit={save}><div className="form-grid"><div><label>Device type</label><input value={device.deviceType || ''} onChange={(e) => setDevice({ ...device, deviceType: e.target.value })} /></div><div><label>Device name</label><input value={device.deviceName || ''} onChange={(e) => setDevice({ ...device, deviceName: e.target.value })} /></div></div>{!device.connected && <button type="button" className="secondary" onClick={connect}>Connect demo wearable</button>}{device.connected && !googleConnected && <button disabled={busy === 'demo'}>{busy === 'demo' ? 'Syncing...' : 'Sync demo device'}</button>}</form></Panel><Panel title="Latest Sync"><div className="stat-grid">{[['Steps', 'dailySteps'], ['Heart rate', 'heartRate'], ['Sleep', 'sleepHours']].map(([label, key]) => <div className="stat" key={key}><strong>{device[key] || 0}</strong><small>{label}</small></div>)}</div><div className="form-grid" style={{ marginTop: '1rem' }}>{['dailySteps', 'heartRate', 'sleepHours'].map((key) => <div key={key}><label>{key}</label><input type="number" value={device[key] || 0} onChange={(e) => setDevice({ ...device, [key]: +e.target.value })} /></div>)}</div>{device.lastSync && <p className="muted">Last sync {new Date(device.lastSync).toLocaleString()}</p>}</Panel></div></div>;
}
