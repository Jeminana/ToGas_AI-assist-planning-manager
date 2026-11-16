import React, {useEffect, useRef, useState} from 'react';
import {req} from './api.js';

export default function Planner({today, tasks, onChanged}) {
  const [date, setDate] = useState(today);
  const [windows, setWindows] = useState([{start: '09:00', end: '12:00'}]);
  const [maxTasks, setMaxTasks] = useState(5);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [plan, setPlan] = useState(null);
  const [fromNow, setFromNow] = useState(false);
  const [retry, setRetry] = useState(0);
  const lock = useRef(false);

  useEffect(() => {setPlan(null);}, [tasks]);
  useEffect(() => {
    let active = true;
    setLoading(true); setPlan(null); setError(''); setMessage(''); setSaved(false);
    req(`/availability?date=${date}`).then(result => {
      if (!active) return;
      setWindows(result.windows.length ? result.windows : [{start: '09:00', end: '12:00'}]);
      setMaxTasks(result.max_tasks); setSaved(result.saved);
    }).catch(error => {if (active) setError(error.message);})
      .finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [date, retry]);

  function edit(next) {setWindows(next); setSaved(false); setPlan(null); setMessage('');}
  async function action(work) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setMessage('');
    try {await work();} catch (error) {setError(error.message);}
    finally {lock.current = false; setBusy(false);}
  }

  return <section className="card stack planner" aria-label="Day planner">
    <h2>Plan your day</h2><p className="hint">Asia/Seoul · Review proposed times before confirming. Confirmed tasks keep their starting times.</p>
    <label>Planning date<input type="date" value={date} required disabled={busy} onChange={event => {if (event.target.value) {setDate(event.target.value); setFromNow(false);}}} /></label>
    <label className="check-label"><input type="checkbox" checked={fromNow} disabled={busy || date !== today} onChange={event => {setFromNow(event.target.checked); setPlan(null);}} />Plan from now (today only)</label>
    {loading ? <p role="status">Loading availability...</p> : <>
      <form className="stack" aria-label="Availability" onSubmit={event => {event.preventDefault(); action(async () => {
        await req('/availability', {method: 'PUT', body: JSON.stringify({date, windows, max_tasks: maxTasks})});
        setSaved(true); setPlan(null); setMessage('Availability saved.'); await onChanged();
      });}}>
        <fieldset disabled={busy}>
          {windows.map((window, index) => <div className="availability-window" key={index}>
            <label>Available start {index + 1}<input type="time" required value={window.start} onChange={event => edit(windows.map((item, i) => i === index ? {...item, start: event.target.value} : item))} /></label>
            <label>Available end {index + 1}<input type="time" required value={window.end} onChange={event => edit(windows.map((item, i) => i === index ? {...item, end: event.target.value} : item))} /></label>
            {windows.length > 1 && <button className="tiny secondary" type="button" aria-label={`Remove window ${index + 1}`} onClick={() => edit(windows.filter((_, i) => i !== index))}>Remove</button>}
          </div>)}
          <button type="button" className="secondary" disabled={windows.length >= 12} onClick={() => edit([...windows, {start: '13:00', end: '17:00'}])}>Add time window</button>
          <label>Maximum tasks per day<input type="number" min="1" max="50" step="1" required value={maxTasks} onChange={event => {setMaxTasks(Number(event.target.value)); setSaved(false); setPlan(null);}} /></label>
        </fieldset>
        <button disabled={busy}>{busy ? 'Working...' : 'Save availability'}</button>
      </form>
      <button disabled={busy || !saved} onClick={() => action(async () => {
        const result = await req('/planning/propose', {method: 'POST', body: JSON.stringify({date, plan_from_now: fromNow})}); setPlan(result);
      })}>Generate plan</button>
      {!saved && <p className="hint">Save availability to enable planning.</p>}
    </>}
    {busy && <p role="status">Updating plan...</p>}
    {error && <div className="notice" role="alert">{error}<button className="secondary" disabled={busy} onClick={() => setRetry(value => value + 1)}>Reload availability</button></div>}
    {message && <p role="status">{message}</p>}
    {plan && <div aria-label="Proposed schedule">
      <h3>Proposed schedule</h3><p className="hint">No task times have been saved. Unknown durations use {plan.provisional_minutes} minutes provisionally, without changing the task estimate.</p>
      {plan.planning_from && <p className="notice">Planning from {plan.planning_from.replace('T', ' ').slice(0, 16)} Seoul. Existing confirmed times are preserved.</p>}
      {plan.placements.length ? plan.placements.map(item => <article className="placement" key={item.task_id}>
        <strong>{item.title}</strong><p>{item.start.slice(11, 16)}–{item.end.slice(11, 16)} · {item.minutes} min{item.provisional ? ' (provisional estimate)' : ''}</p><details className="task-metadata"><summary>Why this task?</summary><small>{item.explanation}</small></details>
      </article>) : <p>No new placements fit this day. Review the reasons below or change availability.</p>}
      {plan.confirmed.length > 0 && <><h3>Already confirmed</h3>{plan.confirmed.map(item => <p key={item.task_id}>{item.start.slice(11, 16)} · {item.title} · {item.minutes} min{item.provisional ? ' (provisional)' : ''}</p>)}</>}
      {plan.conflicts.length > 0 && <><h3>Scheduling conflicts</h3>{plan.conflicts.map((item, i) => <p className="notice" key={i}>{item.reason}</p>)}</>}
      {plan.unscheduled.length > 0 && <><h3>Not placed</h3>{plan.unscheduled.map(item => <p key={item.task_id}><strong>{item.title}</strong>: {item.reason}</p>)}</>}
      <div className="buttons wrap"><button disabled={busy || !plan.placements.length} onClick={() => action(async () => {
        await req('/planning/confirm', {method: 'POST', body: JSON.stringify({plan})});
        setPlan(null); setMessage('Schedule confirmed.'); await onChanged();
      })}>Confirm plan</button><button className="secondary" disabled={busy} onClick={() => {setPlan(null); setMessage('Plan rejected. Task times are unchanged.');}}>Reject plan</button></div>
    </div>}
  </section>;
}
