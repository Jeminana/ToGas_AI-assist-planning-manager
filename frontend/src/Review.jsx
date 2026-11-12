import React from 'react';
import TaskFields from './TaskFields.jsx';

export default function Review({proposals, setProposals, saving, onApprove, warnings, provider, info, onJournal, onTasks}) {
  const change = (id, next) => setProposals(current => current.map(item => item._id === id ? next : item));
  return <>
    <h1>Review suggestions</h1><p>Edit suggestions before saving. Nothing becomes a task until you approve it.</p>
    {provider === 'jev' && info.cached && <p className="notice">Reused a recent Jev analysis. No new API request was made.</p>}
    {info.total > 0 && <p>{proposals.length} of {info.total} suggestions left to review.</p>}
    {warnings.map((warning, index) => <p className="notice" key={index}>{warning}</p>)}
    {proposals.length ? proposals.map(proposal => <div className="card" key={proposal._id}>
      <TaskFields value={proposal} onChange={next => change(proposal._id, next)} disabled={saving} />
      {provider !== 'mock' && <p>Action probability: {(proposal.action_probability * 100).toFixed(0)}% · category confidence: {(proposal.category_confidence * 100).toFixed(0)}% · urgency confidence: {(proposal.urgency_confidence * 100).toFixed(0)}%</p>}
      {proposal.needs_review && <small>Needs review — {provider === 'mock' ? 'demo suggestion' : 'uncertain prediction'}</small>}
      {proposal.review_reasons?.length > 0 && <ul className="review-reasons">{proposal.review_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
      {proposal.source_text && <details className="source-text"><summary>Original journal text</summary><p>{proposal.source_text}</p></details>}
      {proposal.title_truncated && <p className="notice">The original sentence was shortened to 250 characters. Check the title before saving.</p>}
      <div className="buttons"><button disabled={saving || !proposal.title.trim()} onClick={() => onApprove(proposal)}>Approve</button><button disabled={saving} className="secondary" onClick={() => setProposals(current => current.filter(item => item._id !== proposal._id))}>Reject</button></div>
    </div>) : info.total > 0 ? <p>All suggestions reviewed. Only approved suggestions were saved.</p> : <p>No actionable tasks were found. Your journal is saved. You can edit it or add a task manually.</p>}
    {saving && <p role="status">Saving task...</p>}<div className="buttons wrap"><button className="secondary" onClick={onJournal}>Back to journal</button><button className="secondary" onClick={onTasks}>Go to Tasks</button></div>
  </>;
}
