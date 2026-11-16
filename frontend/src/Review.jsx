import React from 'react';
import TaskFields from './TaskFields.jsx';

export default function Review({proposals, setProposals, saving, onApprove, warnings, provider, info, onJournal, onTasks, manualDraft, setManualDraft, addingManual, setAddingManual, onManualAdd}) {
  const change = (id, next) => setProposals(current => current.map(item => item._id === id ? next : item));
  return <>
    <h1>Review suggestions</h1><p>Edit suggestions before saving. Nothing becomes a task until you approve it.</p>
    <p>Extracted {info.total} task suggestion{info.total === 1 ? '' : 's'}.</p>
    {provider === 'mock' && <p className="hint">Demo results — these are rule-based suggestions, not Jev predictions.</p>}
    {provider === 'jev' && info.cached && <p className="notice">Reused a recent Jev analysis. No new API request was made.</p>}
    {info.total > 0 && <p>{proposals.length} of {info.total} suggestions left to review.</p>}
    {warnings.map((warning, index) => <p className="notice" key={index}>{warning}</p>)}
    {provider === 'jev' && info.model && <details className="source-text"><summary>Analysis details</summary><p>Model: {info.model}{Number.isFinite(info.latency) ? ` · Analysis time: ${info.latency} ms` : ''}</p>
      {info.usage && <p>Reported tokens: {info.usage.input_tokens ?? 'unavailable'} input · {info.usage.output_tokens ?? 'unavailable'} output{info.cached ? ' (original cached request)' : ''}</p>}
    </details>}
    {proposals.length ? proposals.map(proposal => <div className="card" key={proposal._id}>
      <TaskFields value={proposal} onChange={next => change(proposal._id, next)} disabled={saving} />
      {provider !== 'mock' && <details className="source-text"><summary>Prediction details</summary><p>{[
        ['Action probability', proposal.action_probability], ['category confidence', proposal.category_confidence], ['urgency confidence', proposal.urgency_confidence],
      ].map(([label, value]) => `${label}: ${typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(0)}%` : 'not provided'}`).join(' · ')}</p></details>}
      {proposal.needs_review && <small>Needs review — {provider === 'mock' ? 'demo suggestion' : 'uncertain prediction'}</small>}
      {proposal.review_reasons?.length > 0 && <ul className="review-reasons">{proposal.review_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
      {proposal.source_text && <details className="source-text"><summary>Original journal text</summary><p>{proposal.source_text}</p></details>}
      {proposal.title_truncated && <p className="notice">The original sentence was shortened to 250 characters. Check the title before saving.</p>}
      <div className="buttons"><button disabled={saving || !proposal.title.trim()} onClick={() => onApprove(proposal)}>Approve</button><button disabled={saving} className="secondary" onClick={() => setProposals(current => current.filter(item => item._id !== proposal._id))}>Reject</button></div>
    </div>) : info.total > 0 ? <p>All suggestions reviewed. Only approved suggestions were saved.</p> : <p>No actionable tasks were found. Your journal is saved. You can edit it or add a task manually.</p>}
    <button className="secondary" disabled={saving} aria-expanded={addingManual} onClick={() => setAddingManual(!addingManual)}>{addingManual ? 'Close missing task form' : 'Add a missing task'}</button>
    {addingManual && <form className="card stack" aria-label="Missing task" onSubmit={event => {event.preventDefault(); onManualAdd();}}>
      <TaskFields value={manualDraft} onChange={setManualDraft} disabled={saving} titleLabel="Missing task title" />
      <button disabled={saving || !manualDraft.title.trim()}>{saving ? 'Saving...' : 'Approve manual task'}</button>
    </form>}
    {saving && <p role="status">Saving task...</p>}<div className="buttons wrap"><button className="secondary" onClick={onJournal}>Back to journal</button><button className="secondary" onClick={onTasks}>Go to Tasks</button></div>
  </>;
}
