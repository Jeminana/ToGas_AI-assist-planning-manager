import React, {useState} from 'react';
import TaskFields, {TaskMeta} from './TaskFields.jsx';

function TaskRow({task, pending, onPatch, onRemove}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(task);
  if (editing) return <form className="card stack" aria-label={`Edit ${task.title}`} onSubmit={async event => {
    event.preventDefault();
    if (await onPatch(task, {title: draft.title, category: draft.category, urgency_score: draft.urgency_score, due_date: draft.due_date || null})) setEditing(false);
  }}>
    <TaskFields value={draft} onChange={setDraft} disabled={pending} titleLabel="Edit task title" />
    <div className="buttons"><button disabled={pending || !draft.title.trim()}>{pending ? 'Saving...' : 'Save changes'}</button><button type="button" className="secondary" disabled={pending} onClick={() => setEditing(false)}>Cancel</button></div>
  </form>;
  return <div className="task">
    <input type="checkbox" aria-label={`${task.done ? 'Reopen' : 'Complete'} ${task.title}`} checked={!!task.done} disabled={pending} onChange={() => onPatch(task, {done: !task.done})} />
    <div className="task-content"><span className={task.done ? 'done' : ''}>{task.title}</span><TaskMeta task={task} /></div>
    <div className="task-actions"><button className="tiny secondary" disabled={pending} onClick={() => {setDraft(task); setEditing(true);}}>Edit</button><button className="tiny secondary" disabled={pending} onClick={() => onRemove(task)}>Delete</button></div>
  </div>;
}

export default function TaskList({tasks, pendingIds, onPatch, onRemove, emptyText = 'No tasks yet. Add one above or start with a Brain Dump.'}) {
  return tasks.length ? tasks.map(task => <TaskRow key={task.id} task={task} pending={pendingIds.has(task.id)} onPatch={onPatch} onRemove={onRemove} />) : <p>{emptyText}</p>;
}
