import React from 'react';

export const blankTask = {title: '', category: 'other', urgency_score: 1, due_date: ''};

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
  </fieldset>;
}

export function TaskMeta({task}) {
  return <small>{task.category} · urgency {task.urgency_score.toFixed(2)}{task.due_date ? ` · due ${task.due_date}` : ' · no deadline'}</small>;
}
