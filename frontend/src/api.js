const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export async function req(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: {'Content-Type': 'application/json', ...options.headers},
  });
  if (!response.ok) {
    let detail;
    try { ({detail} = await response.json()); } catch {}
    const message = Array.isArray(detail)
      ? detail.map(issue => `${issue.loc?.slice(1).join('.') || 'Input'}: ${issue.msg}`).join('; ')
      : typeof detail === 'string' ? detail : null;
    throw new Error(message || `Request failed (HTTP ${response.status}). Please try again.`);
  }
  return response.status === 204 ? null : response.json();
}

export {localDate} from './date.js';

export function sortTasks(tasks) {
  return [...tasks].sort((a, b) => a.done - b.done || b.urgency_score - a.urgency_score || b.id - a.id);
}
