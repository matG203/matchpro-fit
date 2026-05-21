import { useEffect, useState } from 'react';
import { Empty, Panel } from '../components/ui';
import api from '../lib/api';

export default function WorkoutsPage() {
  const [workouts, setWorkouts] = useState<any[]>([]);
  useEffect(() => { api.get('/workout').then((response) => setWorkouts(response.data)); }, []);
  return <div className="page"><h1>Workout History</h1><Panel title={`${workouts.length} sessions`}>{workouts.length ? <ul className="list">{workouts.map((workout) => <li key={workout.id} className="between"><span><b>{workout.type}</b><br /><small>{new Date(workout.completedAt).toLocaleString()} | {workout.duration} minutes | {workout.intensity}</small></span><strong>+{workout.xpEarned} XP</strong></li>)}</ul> : <Empty>Logged workouts build your streak here.</Empty>}</Panel></div>;
}
