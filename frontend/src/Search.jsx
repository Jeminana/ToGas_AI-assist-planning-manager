import React, {useEffect, useState} from 'react';
import {req} from './api.js';
import {TaskMeta} from './TaskFields.jsx';

export default function Search({onFocus, onOpenJournal}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({tasks: [], journals: []});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setResults({tasks: [], journals: []});
    if (!query.trim()) {setBusy(false); return () => controller.abort();}
    setBusy(true);
    const timer = setTimeout(async () => {
      try {setResults(await req(`/search?q=${encodeURIComponent(query)}`, {signal: controller.signal}));}
      catch (error) {if (!controller.signal.aborted) setError(error.message);}
      finally {if (!controller.signal.aborted) setBusy(false);}
    }, 200);
    return () => {clearTimeout(timer); controller.abort();};
  }, [query]);
  return <>
    <h1>Search</h1><label>Search tasks and journals<input type="search" maxLength={200} value={query} onChange={event => setQuery(event.target.value)} /></label>
    {error && <p role="alert">{error}</p>}
    {busy ? <p role="status">Searching...</p> : !query.trim() ? <p>Enter a keyword to find tasks and journal entries.</p> : <>
      <h2>Tasks ({results.tasks.length})</h2>{results.tasks.map(task => <article className="card" key={task.id}><h3 className={task.done ? 'done' : ''}>{task.title}</h3><TaskMeta task={task} />{!task.done && <div><button onClick={() => onFocus(task)}>Start focusing</button></div>}</article>)}
      <h2>Journals ({results.journals.length})</h2>{results.journals.map(entry => <article className="card journal-entry" key={entry.id}><p>{entry.content}</p><button className="secondary" onClick={() => onOpenJournal(entry)}>Open entry</button></article>)}
      {!results.tasks.length && !results.journals.length && <p>No matches found. Try another keyword.</p>}
    </>}
  </>;
}
