import { useEffect, useRef, useState } from 'react'
import {
  checkStatus, createSession, getSessionState,
  sendIntake, generateScenarios, runAnalysis,
  getRankedScenarios,
} from './api'
import type { FormData, RankedScenario } from './types'
import IntakeForm from './components/IntakeForm'
import ChatView from './components/ChatView'
import ScenarioCards from './components/ScenarioCards'

type Phase = 'checking' | 'idle' | 'intake' | 'chat' | 'analyzing' | 'results' | 'error'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface PersistedSession {
  sessionId: string
  chatMessages: ChatMessage[]
  profileComplete: boolean
}

const STORAGE_KEY = 'second_brain_session'

function saveToStorage(data: PersistedSession) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch { /* ignore */ }
}

function loadFromStorage(): PersistedSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function clearStorage() {
  localStorage.removeItem(STORAGE_KEY)
}


function App() {
  const [phase, setPhase]               = useState<Phase>('checking')
  const [sessionId, setSessionId]       = useState<string | null>(null)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatLoading, setChatLoading]   = useState(false)
  const [profileComplete, setProfileComplete] = useState(false)
  const [ranked, setRanked]             = useState<RankedScenario[]>([])
  const [total, setTotal]               = useState(0)
  const [showingAll, setShowingAll]     = useState(false)
  const [progressMessages, setProgressMessages] = useState<string[]>([])
  const [error, setError]               = useState<string | null>(null)

  // Persist session to localStorage whenever key state changes
  const persistRef = useRef({ sessionId, chatMessages, profileComplete })
  useEffect(() => {
    persistRef.current = { sessionId, chatMessages, profileComplete }
    if (sessionId && (phase === 'chat' || phase === 'results')) {
      saveToStorage({ sessionId, chatMessages, profileComplete })
    }
  }, [sessionId, chatMessages, profileComplete, phase])

  // On mount: check backend, then try to resume saved session
  useEffect(() => {
    checkStatus()
      .then(() => tryResume())
      .catch(() => setPhase('error'))
  }, [])

  async function tryResume() {
    const saved = loadFromStorage()
    if (!saved) { setPhase('idle'); return }

    try {
      const state = await getSessionState(saved.sessionId)

      setSessionId(saved.sessionId)

      if (state.phase === 'exploration') {
        // Analysis already done — jump straight to results
        const res = await getRankedScenarios(saved.sessionId, 5)
        setRanked(res.ranked)
        setTotal(res.total)
        setPhase('results')
      } else {
        // Resume chat; if backend phase is 'scenarios' profile was already complete
        const pc = saved.profileComplete || state.phase === 'scenarios'
        setChatMessages(saved.chatMessages)
        setProfileComplete(pc)
        setPhase('chat')
      }
    } catch {
      // Session gone (backend restarted and sessions/ was cleared, or expired)
      clearStorage()
      setPhase('idle')
    }
  }

  function handleStartFresh() {
    clearStorage()
    setSessionId(null)
    setChatMessages([])
    setProfileComplete(false)
    setPhase('idle')
  }

  async function handleStart() {
    try {
      const id = await createSession()
      setSessionId(id)
      setPhase('intake')
    } catch (e: any) {
      setError(e.message); setPhase('error')
    }
  }

  async function handleIntakeSubmit(formData: FormData) {
    if (!sessionId) return
    setChatLoading(true)
    try {
      const res = await sendIntake(
        sessionId,
        'Here is my situation. Please ask any follow-up questions you need to build my profile.',
        formData,
      )
      const msgs: ChatMessage[] = [{ role: 'assistant', content: res.reply }]
      setChatMessages(msgs)
      setProfileComplete(res.profile_complete)
      setPhase('chat')
    } catch (e: any) {
      setError(e.message); setPhase('error')
    } finally {
      setChatLoading(false)
    }
  }

  async function handleChatSend(text: string) {
    if (!sessionId) return
    const updated: ChatMessage[] = [...chatMessages, { role: 'user', content: text }]
    setChatMessages(updated)
    setChatLoading(true)
    try {
      const res = await sendIntake(sessionId, text)
      const final = [...updated, { role: 'assistant' as const, content: res.reply }]
      setChatMessages(final)
      setProfileComplete(res.profile_complete)
    } catch (e: any) {
      setError(e.message); setPhase('error')
    } finally {
      setChatLoading(false)
    }
  }

  async function handleClarify() {
    if (!sessionId) return
    setProfileComplete(false)
    setChatLoading(true)
    try {
      const res = await sendIntake(sessionId, 'I would like to clarify or add more details to my profile.')
      const appended: ChatMessage[] = [
        ...chatMessages,
        { role: 'user', content: 'I would like to clarify or add more details.' },
        { role: 'assistant', content: res.reply },
      ]
      setChatMessages(appended)
      setProfileComplete(res.profile_complete)
    } catch (e: any) {
      setError(e.message); setPhase('error')
    } finally {
      setChatLoading(false)
    }
  }

  async function runAnalysisFlow(sid: string) {
    setPhase('analyzing')
    setProgressMessages(['Generating scenarios…'])

    try {
      await generateScenarios(sid)

      // Open SSE stream before calling runAnalysis so no events are missed
      await new Promise<void>((resolve, reject) => {
        const source = new EventSource(`/api/analysis/stream/${sid}`)

        source.onmessage = (e) => {
          const data = JSON.parse(e.data)
          if (data.done) {
            source.close()
            resolve()
          } else if (data.message) {
            setProgressMessages(prev => [...prev, data.message])
          }
        }

        source.onerror = () => {
          source.close()
          reject(new Error('Progress stream disconnected'))
        }

        // Start analysis after SSE is open
        runAnalysis(sid).catch(err => {
          source.close()
          reject(err)
        })
      })

      setProgressMessages(prev => [...prev, 'Ranking scenarios…'])
      const res = await getRankedScenarios(sid, 5)
      setRanked(res.ranked)
      setTotal(res.total)
      setPhase('results')
    } catch (e: any) {
      setError(e.message); setPhase('error')
    }
  }

  async function handleShowMore() {
    if (!sessionId) return
    try {
      const res = await getRankedScenarios(sessionId, total)
      setRanked(res.ranked)
      setShowingAll(true)
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Second Brain</h1>
        <p className="tagline">AI-powered life-decision simulator</p>
      </header>

      <main className="app-main">

        {phase === 'checking' && (
          <div className="status-card status-checking">
            <span className="status-dot" /><span>Connecting…</span>
          </div>
        )}

        {phase === 'error' && (
          <div className="status-card status-error">
            <span className="status-dot" /><span>{error ?? 'Backend unreachable'}</span>
          </div>
        )}

        {phase === 'idle' && (
          <div className="idle-view">
            <div className="status-card status-ok" style={{ marginBottom: '2rem' }}>
              <span className="status-dot" /><span>Backend connected</span>
            </div>
            <div className="hero-card card">
              <h2>Make your next big decision with clarity</h2>
              <p>Describe your situation, and we'll simulate multiple realistic paths — ranked by outcomes, backed by research and Monte Carlo analysis.</p>
              <button className="btn-primary" onClick={handleStart}>Get started →</button>
            </div>
          </div>
        )}

        {phase === 'intake' && (
          <IntakeForm onSubmit={handleIntakeSubmit} loading={chatLoading} />
        )}

        {phase === 'chat' && (
          <div className="chat-phase">
            <div className="chat-phase-header">
              <button className="btn-start-fresh" onClick={handleStartFresh}>
                ← Start fresh
              </button>
            </div>
            <ChatView
              messages={chatMessages}
              onSend={handleChatSend}
              onProceed={() => sessionId && runAnalysisFlow(sessionId)}
              onClarify={handleClarify}
              loading={chatLoading}
              profileComplete={profileComplete}
            />
          </div>
        )}

        {phase === 'analyzing' && (
          <div className="analyzing-view card">
            <div className="analyzing-spinner" />
            <h3>Analyzing your decision…</h3>
            <div className="progress-log">
              {progressMessages.map((msg, i) => (
                <div key={i} className={`progress-line ${i === progressMessages.length - 1 ? 'active' : 'done'}`}>
                  <span className="progress-icon">{i === progressMessages.length - 1 ? '⟳' : '✓'}</span>
                  <span>{msg}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {phase === 'results' && (
          <>
            <div style={{ width: '100%', display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
              <button className="btn-start-fresh" onClick={handleStartFresh}>← Start fresh</button>
            </div>
            <ScenarioCards
              ranked={ranked}
              total={total}
              onShowMore={handleShowMore}
              showingAll={showingAll}
            />
          </>
        )}

      </main>
    </div>
  )
}

export default App
