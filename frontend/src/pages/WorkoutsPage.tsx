import { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Empty, Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

export default function WorkoutsPage() {
  const [workouts, setWorkouts] = useState<any[]>([]);
  const [message, setMessage] = useState('');

  function load() {
    api.get('/workout').then((response) => setWorkouts(response.data)).catch((error) => setMessage(errorMessage(error)));
  }

  useEffect(() => { load(); }, []);

  async function removeWorkout(id: string) {
    if (!confirm('Remove this workout log and take back its XP?')) return;
    try {
      await api.delete(`/workout/${id}`);
      setWorkouts((current) => current.filter((workout) => workout.id !== id));
      setMessage('Workout log removed.');
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  return (
    <div className="page">
      <h1>Workout History</h1>
      <Panel title={`${workouts.length} sessions`}>
        {message && <p className={message.includes('removed') ? 'success' : 'error'}>{message}</p>}
        {workouts.length ? (
          <ul className="list">
            {workouts.map((workout) => (
              <li key={workout.id} className="between">
                <span>
                  <b>{workout.type}</b><br />
                  <small>{new Date(workout.completedAt).toLocaleString()} | {workout.duration} minutes | {workout.intensity}</small>
                </span>
                <span className="actions">
                  <strong>+{workout.xpEarned} XP</strong>
                  <button className="ghost compact" onClick={() => removeWorkout(workout.id)}><Trash2 size={15} /> Remove</button>
                </span>
              </li>
            ))}
          </ul>
        ) : <Empty>Logged workouts build your streak here.</Empty>}
      </Panel>
    </div>
  );
}
