import { useMemo } from 'react'

function formatDate(isoString) {
  const d = new Date(isoString)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

function SessionInspector({ actions, loading }) {
  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-slate-200 rounded w-1/3" />
          <div className="h-4 bg-slate-200 rounded w-full" />
          <div className="h-4 bg-slate-200 rounded w-5/6" />
          <div className="h-4 bg-slate-200 rounded w-2/3" />
        </div>
      </div>
    )
  }

  if (!actions || actions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a session to inspect its actions.
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Session Inspector</h2>
        <p className="text-sm text-slate-500">{actions.length} action{actions.length === 1 ? '' : 's'} recorded</p>
      </div>

      {actions.map((action) => (
        <div key={action.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-slate-500">{formatDate(action.timestamp)}</span>
            <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full">
              Action #{action.id}
            </span>
          </div>

          <div className="mb-4">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Input Query</p>
            <p className="text-sm text-slate-900 leading-relaxed">{action.input_query}</p>
          </div>

          {action.extracted_entities && action.extracted_entities.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Extracted Biomedical Entities</p>
              <div className="flex flex-wrap gap-2">
                {action.extracted_entities.map((entity, idx) => (
                  <BiomedicalEntityBadge key={idx} entity={entity} />
                ))}
              </div>
            </div>
          )}

          {action.retrieved_evidence && action.retrieved_evidence.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Retrieved Sentence-Level Evidence</p>
              <div className="space-y-2">
                {action.retrieved_evidence.map((evidence, idx) => {
                  const sentence = typeof evidence === 'string' ? evidence : evidence.sentence
                  const source = typeof evidence === 'string' ? null : evidence.source
                  return (
                    <div key={idx} className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                      <p className="text-sm text-slate-800 leading-relaxed">{sentence}</p>
                      {source && (
                        <span className="mt-1 inline-block text-xs text-slate-500 font-mono">{source}</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {action.generated_answer && (
            <div className="mb-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Generated Answer</p>
              <p className="text-sm text-slate-900 leading-relaxed">{action.generated_answer}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default SessionInspector
