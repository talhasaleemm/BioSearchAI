import { useMemo } from 'react'
import { mockSessions } from '../services/api'

function Sidebar({ sessions, selectedSessionId, onSelectSession, onNewSession }) {
  const displaySessions = useMemo(() => {
    if (sessions && sessions.length > 0) return sessions
    return mockSessions
  }, [sessions])

  return (
    <aside className="w-80 bg-white border-r border-slate-200 flex flex-col shrink-0">
      <div className="p-4 border-b border-slate-200">
        <button
          onClick={onNewSession}
          className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 text-sm transition-colors"
        >
          + New Session
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {displaySessions.map((session) => {
          const isSelected = selectedSessionId === session.id
          return (
            <button
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              className={`w-full text-left rounded-lg border px-3 py-3 transition-colors ${
                isSelected
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-transparent hover:bg-slate-50 hover:border-slate-200'
              }`}
            >
              <p className="text-sm font-medium text-slate-900 truncate">{session.session_name || 'Untitled Session'}</p>
              <p className="text-xs text-slate-500 mt-1 truncate">{session.query_summary || 'No summary available'}</p>
              <p className="text-xs text-slate-400 mt-2">
                {new Date(session.created_at).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </p>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

export default Sidebar
