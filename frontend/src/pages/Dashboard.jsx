import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import SessionInspector from '../components/SessionInspector'
import { getSessions, getSessionActions, mockActions } from '../services/api'

function Dashboard() {
  const [sessions, setSessions] = useState([])
  const [selectedSessionId, setSelectedSessionId] = useState(null)
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingActions, setLoadingActions] = useState(false)

  useEffect(() => {
    async function loadSessions() {
      setLoading(true)
      try {
        const data = await getSessions()
        setSessions(data)
        if (data && data.length > 0 && !selectedSessionId) {
          setSelectedSessionId(data[0].id)
        }
      } catch (err) {
        console.error('Failed to load sessions', err)
      } finally {
        setLoading(false)
      }
    }

    loadSessions()
  }, [])

  useEffect(() => {
    if (!selectedSessionId) {
      setActions([])
      return
    }

    async function loadActions() {
      setLoadingActions(true)
      try {
        const data = await getSessionActions(selectedSessionId)
        setActions(data)
      } catch (err) {
        console.error('Failed to load actions', err)
        setActions(mockActions.filter((a) => a.session_id === Number(selectedSessionId)))
      } finally {
        setLoadingActions(false)
      }
    }

    loadActions()
  }, [selectedSessionId])

  const handleNewSession = () => {
    setSelectedSessionId(null)
    setActions([])
  }

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar
        sessions={sessions}
        selectedSessionId={selectedSessionId}
        onSelectSession={setSelectedSessionId}
        onNewSession={handleNewSession}
      />

      <main className="flex-1 overflow-y-auto">
        <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">BioSearchAI Dashboard</h1>
            <p className="text-sm text-slate-500">Session history and biomedical retrieval workspace</p>
          </div>
          <div className="text-xs text-slate-400">
            Backend: http://localhost:8000
          </div>
        </header>

        <SessionInspector actions={actions} loading={loadingActions} />
      </main>
    </div>
  )
}

export default Dashboard
