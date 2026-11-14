// One save at a time, including repeated clicks before React renders again.
export function createTaskSaver({request, onPendingChange, onSaved, onError}) {
  let pending = false;
  const attempts = new Map();

  return async function saveTask(task, onSuccess = () => {}) {
    if (pending) return false;
    pending = true;
    onPendingChange(true);
    onError('');

    try {
      const payload = JSON.stringify({
        title: task.title,
        category: task.category ?? 'other',
        urgency_score: task.urgency_score ?? 1,
        ...('due_date' in task ? {due_date: task.due_date || null} : {}),
        ...('journal_id' in task ? {journal_id: task.journal_id} : {}),
        ...Object.fromEntries(['importance', 'estimated_minutes', 'effort_level', 'scheduled_start'].filter(key => key in task).map(key => [key, task[key] === '' ? null : task[key]])),
      });
      // Retain the token after failure: the server may already have committed.
      const key = JSON.stringify([task._id ?? 'manual', payload]);
      if (!attempts.has(key)) attempts.set(key, crypto.randomUUID());
      const saved = await request('/tasks', {
        method: 'POST',
        body: JSON.stringify({...JSON.parse(payload), request_id: attempts.get(key)}),
      });
      attempts.delete(key);
      onSaved(saved);
      onSuccess();
      return true;
    } catch (error) {
      onError(error.message);
      return false;
    } finally {
      pending = false;
      onPendingChange(false);
    }
  };
}
