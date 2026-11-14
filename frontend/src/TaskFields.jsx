import React from 'react';

export const blankTask = {title: '', category: 'other', urgency_score: 1, due_date: '', importance: 3, estimated_minutes: null, effort_level: 3, scheduled_start: null};

export default function TaskFields({value, onChange, disabled = false, titleLabel = 'Task title'}) {
  const change = (field, next) => onChange({...value, [field]: next});
  return <fieldset disabled={disabled} className="task-fields">
    <label>{titleLabel}<input aria-label={titleLabel} value={value.title} onChange={event => change('title', event.target.value)} placeholder="Add a task manually" /></label>
    <div className="field-grid">
      <label>Category<select value={value.category} onChange={event => change('category', event.target.value)}>
        {['study', 'work', 'personal', 'health', 'other'].map(category => <option key={category} value={category}>{category[0].toUpperCase() + category.slice(1)}</option>)}
      </select></label>
      <label>Urgency<select value={value.urgency_score} onChange={event => change('urgency_score', Number(event.target.value))}>
        {['Not urgent', 'Low', 'Moderate', 'High'].map((label, index) => <option key={index} value={index}>{label}</option>)}
      </select></label>
    </div>
    <label>Due date<input type="date" value={value.due_date || ''} onChange={event => change('due_date', event.target.value)} /></label>
    <details className="planning-fields"><summary>Planning details</summary>
      <div className="field-grid">
        <label>Importance (1–5)<input type="number" min="1" max="5" step="1" value={value.importance ?? 3} onChange={event => change('importance', Number(event.target.value))} /></label>
        <label>Effort (1–5)<input type="number" min="1" max="5" step="1" value={value.effort_level ?? 3} onChange={event => change('effort_level', Number(event.target.value))} /></label>
      </div>
      <label>Estimated minutes (optional)<input type="number" min="1" max="1440" step="1" value={value.estimated_minutes ?? ''} onChange={event => change('estimated_minutes', event.target.value === '' ? null : Number(event.target.value))} /></label>
      <label>Confirmed start (Seoul, optional)<input type="datetime-local" value={value.scheduled_start || ''} onChange={event => change('scheduled_start', event.target.value || null)} /></label>
      <p className="hint">A starting time is confirmed when you save. Leave it blank to review a proposed schedule on Today. Unknown durations use a provisional 30-minute planning estimate.</p>
    </details>
  </fieldset>;
}

export function TaskMeta({task}) {
  return <small>{task.category} · urgency {task.urgency_score.toFixed(2)} · importance {task.importance ?? 3}/5 · effort {task.effort_level ?? 3}/5{task.due_date ? ` · due ${task.due_date}` : ' · no deadline'}
    {task.scheduled_start ? <><br /><time dateTime={task.scheduled_start}>{task.scheduled_start.replace('T', ' ').slice(0, 16)}</time> Seoul · {task.scheduled_minutes} min{task.scheduled_provisional ? ' (provisional)' : ''} · confirmed</> : <> · unscheduled{task.estimated_minutes ? ` · ${task.estimated_minutes} min` : ' · duration unknown'}</>}
  </small>;
}
