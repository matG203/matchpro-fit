import { FormEvent, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

export default function WearablesPage() {
  const [device, setDevice] = useState<any>({ deviceType: 'watch', deviceName: 'MatchFit Sync', connected: false, dailySteps: 8000, heartRate: 62, sleepHours: 7.5 });
  const [fitbitReady, setFitbitReady] = useState(false);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [search, setSearch] = useSearchParams();
  const load = () => api.get('/wearables').then(({ data }) => { setDevice((current: any) => ({ ...current, ...data.device })); setFitbitReady(data.fitbitReady); });
  useEffect(() => { load(); if (search.get('fitbit') === 'connected') { setMessage('Fitbit connected. Press Sync Fitbit to pull today\'s tracker data.'); setSearch({}, { replace: true }); } }, []);
  async function save(event: FormEvent) { event.preventDefault(); setBusy('demo'); try { const { data } = await api.put('/wearables', device); setDevice(data.device); setMessage(data.readiness ? `Demo sync logged to Health. Readiness is ${data.readiness.score}%.` : 'Demo device saved.'); } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(''); } }
  function connect() { setDevice((current: any) => ({ ...current, connected: true })); setMessage('Device ready. Press Sync device to send its numbers into Health.'); }
  async function connectFitbit() {
    setBusy('fitbit');
    try { const { data } = await api.get('/wearables/fitbit/connect'); location.assign(data.url); }
    catch (error) { setMessage(errorMessage(error)); setBusy(''); }
  }
  async function syncFitbit() {
    setBusy('sync');
    try { const { data } = await api.post('/wearables/fitbit/sync'); setDevice(data.device); setMessage(`Fitbit synced. Readiness is ${data.readiness.score}%.`); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(''); }
  }
  async function disconnectFitbit() {
    setBusy('disconnect');
    try { const { data } = await api.delete('/wearables/fitbit'); setDevice(data.device); setMessage('Fitbit disconnected.'); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(''); }
  }
  const fitbitConnected = device.provider === 'fitbit' && device.connected;
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Wearable data</p><h1>Wearables</h1></div><span className={`connection-pill ${fitbitConnected ? 'online' : ''}`}>{fitbitConnected ? 'Fitbit connected' : 'No real wearable'}</span></div>{message && <p className={message.match(/failed|not|error/i) ? 'error' : 'success'}>{message}</p>}<Panel title="Fitbit Connection"><p className="muted">Connect Fitbit to import today&apos;s steps, sleep, and resting heart rate into MatchFit Health, readiness, challenges, and XP.</p><div className="actions">{fitbitConnected ? <><button disabled={Boolean(busy)} onClick={syncFitbit}>{busy === 'sync' ? 'Syncing...' : 'Sync Fitbit'}</button><button className="secondary" disabled={Boolean(busy)} onClick={disconnectFitbit}>Disconnect</button></> : <button disabled={!fitbitReady || Boolean(busy)} onClick={connectFitbit}>{fitbitReady ? busy === 'fitbit' ? 'Opening Fitbit...' : 'Connect Fitbit' : 'Fitbit setup needed'}</button>}</div>{!fitbitReady && <p className="muted" style={{ marginTop: '1rem' }}>A Fitbit developer client id and secret must be added to Railway before live Fitbit sign-in can open.</p>}</Panel><div className="grid-2"><Panel title="Demo Sync Fallback"><p className="muted">Use this while testing without a Fitbit account.</p><form className="stack" onSubmit={save}><div className="form-grid"><div><label>Device type</label><input value={device.deviceType || ''} onChange={(e) => setDevice({ ...device, deviceType: e.target.value })} /></div><div><label>Device name</label><input value={device.deviceName || ''} onChange={(e) => setDevice({ ...device, deviceName: e.target.value })} /></div></div>{!device.connected && <button type="button" className="secondary" onClick={connect}>Connect demo wearable</button>}{device.connected && !fitbitConnected && <button disabled={busy === 'demo'}>{busy === 'demo' ? 'Syncing...' : 'Sync demo device'}</button>}</form></Panel><Panel title="Latest Sync"><div className="stat-grid">{[['Steps', 'dailySteps'], ['Heart rate', 'heartRate'], ['Sleep', 'sleepHours']].map(([label, key]) => <div className="stat" key={key}><strong>{device[key] || 0}</strong><small>{label}</small></div>)}</div><div className="form-grid" style={{ marginTop: '1rem' }}>{['dailySteps', 'heartRate', 'sleepHours'].map((key) => <div key={key}><label>{key}</label><input type="number" value={device[key] || 0} onChange={(e) => setDevice({ ...device, [key]: +e.target.value })} /></div>)}</div>{device.lastSync && <p className="muted">Last sync {new Date(device.lastSync).toLocaleString()}</p>}</Panel></div></div>;
}
