// One save at a time, including repeated clicks before React renders again.
export function createTaskSaver({request, onPendingChange, onSaved, onError}) {
  let pending = false;

  return async function saveTask(task, onSuccess = () => {}) {
    if (pending) return false;
    pending = true;
    onPendingChange(true);
    onError('');

    try {
      const saved = await request('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          title: task.title,
          category: task.category ?? 'other',
          urgency_score: task.urgency_score ?? 1,
          ...('due_date' in task ? {due_date: task.due_date || null} : {}),
          ...('journal_id' in task ? {journal_id: task.journal_id} : {}),
        }),
      });
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
