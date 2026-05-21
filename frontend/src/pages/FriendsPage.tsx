import { FormEvent, useEffect, useState } from 'react';
import { AvatarMark, Empty, Panel, Tier } from '../components/ui';
import api, { errorMessage } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function FriendsPage() {
  const me = useAuthStore((state) => state.user);
  const [data, setData] = useState<any>({ friends: [], requests: [], activity: [] });
  const [message, setMessage] = useState('');
  const load = () => api.get('/friends').then((response) => setData(response.data));
  useEffect(() => { load(); }, []);
  async function request(event: FormEvent) {
    event.preventDefault();
    try { await api.post('/friends/request', { username: new FormData(event.target as HTMLFormElement).get('username') }); setMessage('Request sent.'); load(); }
    catch (error) { setMessage(errorMessage(error)); }
  }
  const accept = async (id: string) => { await api.put(`/friends/${id}/accept`); load(); };
  const remove = async (id: string) => { await api.delete(`/friends/${id}`); load(); };
  const player = (link: any) => link.userId === me?.id ? link.friend : link.user;
  return <div className="page"><h1>Friends</h1><div className="grid-2"><Panel title="Find Players"><form className="inline" onSubmit={request}><input name="username" required placeholder="username" /><button>Send request</button></form>{message && <p className={message.includes('sent') ? 'success' : 'error'}>{message}</p>}<h2>Requests</h2>{data.requests.length ? <ul className="list">{data.requests.map((link: any) => <li className="between" key={link.id}><span>{player(link).username}</span>{link.friendId === me?.id ? <button onClick={() => accept(link.id)}>Accept</button> : <button className="secondary" onClick={() => remove(link.id)}>Cancel</button>}</li>)}</ul> : <Empty>No pending requests.</Empty>}</Panel><Panel title="Squad">{data.friends.length ? <ul className="list">{data.friends.map((link: any) => { const friend = player(link); return <li className="between" key={link.id}><span className="inline"><AvatarMark id={friend.avatarId} />{friend.displayName || friend.username}</span><span className="inline"><Tier value={friend.tier} /><button className="secondary" onClick={() => remove(link.id)}>Remove</button></span></li>; })}</ul> : <Empty>Friend leaderboards wake up once a request is accepted.</Empty>}</Panel></div><Panel title="Friends Activity">{data.activity.length ? <ul className="list">{data.activity.map((workout: any) => <li key={workout.id}>{workout.user.username} logged {workout.duration} minutes of {workout.type}.</li>)}</ul> : <Empty>No squad sessions yet.</Empty>}</Panel></div>;
}
