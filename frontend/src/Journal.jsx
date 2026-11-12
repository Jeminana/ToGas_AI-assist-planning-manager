import React from 'react';

export default function Journal({editorRef, text, onChange, onSave, onAnalyze, onNew, canStartNew, busy, savingTask, status, journals, onOpen, provider}) {
  return <>
    <h1>Brain Dump</h1><p>Write freely. Save your thoughts, then review possible next steps.</p>
    <button className="secondary" disabled={busy || !canStartNew} onClick={onNew}>New entry</button>
    {!canStartNew && <p className="hint">Save this entry before starting another.</p>}
    {provider === 'mock' && <p className="notice">Demo mode: suggestions use simple rules, not Jev predictions.</p>}
    {provider === 'jev' && <p className="notice">Live Jev mode: organizing sends this entry for analysis. Identical analyses are reused for 30 minutes to save shared API usage.</p>}
    <label className="sr-only" htmlFor="journal-text">Journal entry</label>
    <textarea ref={editorRef} id="journal-text" value={text} disabled={busy} maxLength={10000} onChange={event => onChange(event.target.value)} placeholder="I need to finish my NLP assignment tomorrow. I feel tired today." />
    <div className="buttons wrap"><button className="secondary" disabled={busy || !text.trim()} onClick={onSave}>Save journal</button><button disabled={busy || savingTask || !text.trim()} onClick={onAnalyze}>{busy ? 'Working...' : provider === 'mock' ? 'Preview suggestions' : 'Organize with Jev'}</button></div>
    {status && <p role="status">{status}</p>}
    <h2>Journal history</h2>
    {journals.length ? journals.map(entry => <article className="card journal-entry" key={entry.id}>
      <time dateTime={entry.created_at}>{new Date(entry.created_at).toLocaleString()}</time><p>{entry.content}</p><button className="secondary" disabled={busy} onClick={() => onOpen(entry)}>Open entry</button>
    </article>) : <p>No saved entries yet. Your journal can be saved without analysis.</p>}
  </>;
}
