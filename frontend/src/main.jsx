import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {req, localDate, sortTasks} from './api.js';
import {createTaskSaver} from './task-save.js';
import TaskFields, {blankTask, TaskMeta} from './TaskFields.jsx';
import TaskList from './TaskList.jsx';
import Journal from './Journal.jsx';
import Review from './Review.jsx';
import Search from './Search.jsx';
import Planner from './Planner.jsx';

function App() {
  const [tab, setTab] = useState('Today');
  const [tasks, setTasks] = useState([]);
  const [journals, setJournals] = useState([]);
  const [journal, setJournal] = useState('');
  const [journalStatus, setJournalStatus] = useState('');
  const [journalBusy, setJournalBusy] = useState(false);
  const journalLock = useRef(false);
  const savedJournal = useRef(null);
  const journalRequest = useRef(null);
  const journalEditor = useRef(null);
  const [journalFocusVersion, setJournalFocusVersion] = useState(0);
  const [proposals, setProposals] = useState([]);
  const [analysisJournalId, setAnalysisJournalId] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [provider, setProvider] = useState('mock');
  const [analysisProvider, setAnalysisProvider] = useState('mock');
  const [analysisInfo, setAnalysisInfo] = useState({total: 0, cached: false});
  const [error, setError] = useState('');
  const [draft, setDraft] = useState({...blankTask});
  const [showTaskForm, setShowTaskForm] = useState(false);
  const taskForm = useRef(null);
  const addTaskButton = useRef(null);
  const [focusId, setFocusId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [pendingIds, setPendingIds] = useState(new Set());
  const mutations = useRef(new Set());
  const [booting, setBooting] = useState(true);
  const [loadVersion, setLoadVersion] = useState(0);
  const [today, setToday] = useState(localDate);
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState('');
  const [dashboardVersion, setDashboardVersion] = useState(0);

  const [addTask] = useState(() => createTaskSaver({
    request: req, onPendingChange: setSaving, onError: setError,
    onSaved: saved => setTasks(current => sortTasks([...current.filter(task => task.id !== saved.id), saved])),
  }));

  useEffect(() => {
    let active = true;
    setBooting(true);
    Promise.allSettled([req('/tasks'), req('/journals'), req('/health')]).then(results => {
      if (!active) return;
      const [taskResult, journalResult, healthResult] = results;
      if (taskResult.status === 'fulfilled') setTasks(taskResult.value);
      if (journalResult.status === 'fulfilled') setJournals(journalResult.value);
      if (healthResult.status === 'fulfilled') setProvider(healthResult.value.ai_mode);
      setError(results.filter(result => result.status === 'rejected').map(result => result.reason.message).join('; '));
      setBooting(false);
    });
    return () => {active = false;};
  }, [loadVersion]);

  useEffect(() => {
    const timer = setInterval(() => setToday(localDate()), 60000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (tab === 'Tasks' && showTaskForm && !booting) taskForm.current?.querySelector('input')?.focus();
  }, [tab, showTaskForm, booting]);

  useEffect(() => {
    if (tab === 'Journal' && journalFocusVersion > 0 && !booting) {
      journalEditor.current?.focus({preventScroll: true});
      journalEditor.current?.scrollIntoView({behavior: 'smooth', block: 'center'});
    }
  }, [tab, journalFocusVersion, booting]);

  function closeTaskForm() {
    setShowTaskForm(false);
    addTaskButton.current?.focus();
  }

  useEffect(() => {
    if (booting) return;
    let active = true;
    setDashboardError('');
    req(`/dashboard?today=${today}`).then(result => {
      if (active) setDashboard(result);
    }).catch(error => {if (active) setDashboardError(error.message);});
    return () => {active = false;};
  }, [tasks, today, booting, dashboardVersion]);

  async function mutateTask(task, changes, deleting = false) {
    if (mutations.current.has(task.id)) return false;
    mutations.current.add(task.id);
    setPendingIds(new Set(mutations.current));
    setError('');
    try {
      const updated = await req(`/tasks/${task.id}`, deleting
        ? {method: 'DELETE'}
        : {method: 'PATCH', body: JSON.stringify(changes)});
      setTasks(current => sortTasks(deleting ? current.filter(item => item.id !== task.id) : current.map(item => item.id === task.id ? updated : item)));
      return true;
    } catch (error) {
      setError(error.message);
      return false;
    } finally {
      mutations.current.delete(task.id);
      setPendingIds(new Set(mutations.current));
    }
  }

  async function persistJournal() {
    if (savedJournal.current?.content === journal) return savedJournal.current;
    if (journalRequest.current?.text !== journal) journalRequest.current = {text: journal, request_id: crypto.randomUUID()};
    const saved = await req('/journals', {method: 'POST', body: JSON.stringify(journalRequest.current)});
    savedJournal.current = saved;
    setJournals(current => [saved, ...current.filter(entry => entry.id !== saved.id)]);
    return saved;
  }

  async function journalAction(analyzing = false) {
    if (journalLock.current || !journal.trim()) return;
    journalLock.current = true;
    setJournalBusy(true);
    setError('');
    setJournalStatus('Saving journal...');
    try {
      const saved = await persistJournal();
      setJournalStatus('Journal saved.');
      if (analyzing) {
        setJournalStatus('Journal saved. Analyzing...');
        const result = await req('/ai/analyze', {method: 'POST', body: JSON.stringify({text: journal, journal_id: saved.id, reference_date: today})});
        setProposals(result.proposals.map(proposal => ({...proposal, _id: crypto.randomUUID()})));
        setAnalysisJournalId(saved.id);
        setWarnings(result.warnings || []);
        setAnalysisProvider(result.provider || provider);
        setAnalysisInfo({total: result.proposals.length, cached: !!result.cached});
        setJournalStatus('Journal saved. Suggestions ready.');
        setTab('Review');
      }
    } catch (error) {
      setError(error.message);
      setJournalStatus(savedJournal.current?.content === journal ? 'Journal saved. Analysis did not finish; you can retry.' : '');
    } finally {
      journalLock.current = false;
      setJournalBusy(false);
    }
  }

  function openJournal(entry) {
    if (journal.trim() && savedJournal.current?.content !== journal) {
      setError('Save your current journal before opening another entry.');
      setTab('Journal');
      setJournalFocusVersion(version => version + 1);
      return;
    }
    savedJournal.current = entry;
    setJournal(entry.content);
    setJournalStatus('Saved entry opened. Editing creates a new entry when saved.');
    setTab('Journal');
    setJournalFocusVersion(version => version + 1);
  }

  function newJournal() {
    savedJournal.current = null;
    journalRequest.current = null;
    setJournal('');
    setJournalStatus('');
    setJournalFocusVersion(version => version + 1);
  }

  function startFocus(task) {
    setFocusId(task.id);
    setTab('Focus');
  }

  const focus = tasks.find(task => task.id === focusId);
  const recommendation = dashboard?.recommendation;
  const listProps = {pendingIds, onPatch: mutateTask, onRemove: task => mutateTask(task, null, true)};

  return <div className="app">
    <header><span className="brand">⚡ ToGas</span><small>One step at a time</small></header>
    <main>
      {error && <div className="alert" role="alert">{error}<button onClick={() => setError('')}>Dismiss</button></div>}
      {booting ? <p role="status">Loading your workspace...</p> : <>
        {tab === 'Today' && <>
          <h1>Let's get things done.</h1><p>{today}</p>
          {dashboardError ? <div className="notice" role="alert">{dashboardError}<button className="secondary" onClick={() => setDashboardVersion(version => version + 1)}>Retry dashboard</button></div> : !dashboard ? <p role="status">Loading today...</p> : <>
            <p>{dashboard.completed} of {dashboard.total} tasks completed</p>
            <progress aria-label="Today's progress" value={dashboard.completed} max={dashboard.total || 1} />
            <div className="card"><h2>Suggested next task</h2>{recommendation ? <>
              <h3>{recommendation.task.title}</h3><p>{recommendation.explanation}</p><button onClick={() => startFocus(recommendation.task)}>Start focusing</button>
            </> : <p>All caught up!</p>}</div>
            <h2>Today's tasks</h2><p className="hint">Overdue and undated tasks, tasks due today, and tasks completed today.</p>
            {dashboard.scheduled_tasks?.length > 0 && <><h3>Confirmed schedule</h3><TaskList tasks={dashboard.scheduled_tasks} {...listProps} /></>}
            <h3>Without a start today</h3>
            <TaskList tasks={dashboard.tasks.filter(task => !(dashboard.scheduled_tasks || []).some(scheduled => scheduled.id === task.id))} {...listProps} emptyText="Nothing waiting for a starting time today." />
            {(dashboard.overdue_tasks?.length > 0 || dashboard.schedule_conflicts?.length > 0) && <section className="notice" aria-label="Planning conflicts"><h3>Overdue and scheduling conflicts</h3>
              {dashboard.overdue_tasks?.map(task => <p key={task.id}>{task.title}: overdue since {task.due_date}.</p>)}
              {dashboard.schedule_conflicts?.map((conflict, index) => <p key={index}>{conflict.task_ids.map(id => tasks.find(task => task.id === id)?.title || `Task ${id}`).join(', ')}: {conflict.reason}</p>)}
            </section>}
          </>}
          <div className="buttons wrap"><button className="secondary" onClick={() => setTab('Journal')}>Brain Dump</button><button className="secondary" onClick={() => setTab('Tasks')}>Manage tasks</button></div>
          <Planner today={today} tasks={tasks} onChanged={async () => {setTasks(await req('/tasks')); setDashboardVersion(version => version + 1);}} />
        </>}
        {tab === 'Journal' && <Journal editorRef={journalEditor} text={journal} onChange={text => {setJournal(text); setJournalStatus('');}} onNew={newJournal} canStartNew={!journal.trim() || savedJournal.current?.content === journal} onSave={() => journalAction()} onAnalyze={() => journalAction(true)} busy={journalBusy} savingTask={saving} status={journalStatus} journals={journals} onOpen={openJournal} provider={provider} />}
        {tab === 'Review' && <Review proposals={proposals} setProposals={setProposals} saving={saving} warnings={warnings} provider={analysisProvider} info={analysisInfo} onJournal={() => {const entry = journals.find(entry => entry.id === analysisJournalId); if (entry) openJournal(entry);}} onTasks={() => setTab('Tasks')} onApprove={proposal => addTask({...proposal, journal_id: analysisJournalId}, () => setProposals(current => current.filter(item => item._id !== proposal._id)))} />}
        {tab === 'Tasks' && <>
          <div className="section-heading"><h1>All Tasks</h1><button ref={addTaskButton} className="add-task-button" aria-label={showTaskForm ? 'Hide new task form' : 'Add task'} aria-expanded={showTaskForm} aria-controls="new-task-form" disabled={saving} onClick={() => showTaskForm ? closeTaskForm() : setShowTaskForm(true)}><span aria-hidden="true">{showTaskForm ? '−' : '+'}</span></button></div>
          {showTaskForm && <form id="new-task-form" ref={taskForm} aria-label="New task" className="card stack" onSubmit={event => {event.preventDefault(); if (draft.title.trim()) addTask(draft, () => {setDraft({...blankTask}); closeTaskForm();});}}>
            <TaskFields value={draft} onChange={setDraft} disabled={saving} titleLabel="New task title" /><div className="buttons"><button disabled={saving || !draft.title.trim()}>{saving ? 'Saving...' : 'Add'}</button><button type="button" className="secondary" disabled={saving} onClick={closeTaskForm}>Close</button></div>
          </form>}
          <TaskList tasks={tasks} {...listProps} emptyText="No tasks yet. Tap + to add your first task." />
        </>}
        {tab === 'Search' && <Search onFocus={startFocus} onOpenJournal={openJournal} />}
        {tab === 'Focus' && <>
          <h1>One task at a time</h1><div className="card">{focus ? <>
            <h2>{focus.title}</h2><TaskMeta task={focus} /><p>Focus on progress, not perfection.</p>
            {focus.done ? <p>This task is already complete.</p> : <button disabled={pendingIds.has(focus.id)} onClick={async () => {if (await mutateTask(focus, {done: true})) setTab('Today');}}>{pendingIds.has(focus.id) ? 'Saving...' : 'Mark as done'}</button>}
          </> : <p>This task is no longer available. Choose another task from Today.</p>}</div>
          <button className="secondary" onClick={() => setTab('Today')}>Back to Today</button>
        </>}
        {tab !== 'Review' && proposals.length > 0 && <button className="secondary review-return" onClick={() => setTab('Review')}>Review suggestions ({proposals.length})</button>}
        {error && <button className="secondary" disabled={saving || journalBusy || pendingIds.size > 0} onClick={() => setLoadVersion(version => version + 1)}>Reload workspace</button>}
      </>}
    </main>
    <nav aria-label="Main navigation">{['Today', 'Journal', 'Tasks', 'Search'].map(name => <button key={name} aria-current={tab === name ? 'page' : undefined} className={tab === name ? 'active' : ''} disabled={booting || journalBusy} onClick={() => setTab(name)}>{name}</button>)}</nav>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
