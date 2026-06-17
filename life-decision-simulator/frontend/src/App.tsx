import { useEffect, useState } from 'react'
import { checkStatus, createSession, sendIntake, generateScenarios, runAnalysis, getRankedScenarios } from './api'
import type { FormData, RankedScenario } from './types'
import IntakeForm from './components/IntakeForm'
import ScenarioCards from './components/ScenarioCards'

type Phase = 'checking' | 'idle' | 'intake' | 'analyzing' | 'results' | 'error'

const STEPS = [
  'Creating session…',
  'Processing your situation…',
  'Generating scenarios…',
  'Researching each path…',
  'Running Monte Carlo simulations…',
  'Ranking scenarios…',
]

function App() {
  const [phase, setPhase]           = useState<Phase>('checking')
  const [sessionId, setSessionId]   = useState<string | null>(null)
  const [ranked, setRanked]         = useState<RankedScenario[]>([])
  const [total, setTotal]           = useState(0)
  const [showingAll, setShowingAll] = useState(false)
  const [step, setStep]             = useState(0)
  const [error, setError]           = useState<string | null>(null)

  useEffect(() => {
    checkStatus()
      .then(() => setPhase('idle'))
      .catch(() => setPhase('error'))
  }, [])

  async function handleStart() {
    try {
      const id = await createSession()
      setSessionId(id)
      setPhase('intake')
    } catch (e: any) {
      setError(e.message)
      setPhase('error')
    }
  }

  async function handleIntakeSubmit(formData: FormData) {
    if (!sessionId) return
    setPhase('analyzing')
    setStep(0)

    try {
      setStep(1)
      await sendIntake(sessionId, 'Please analyze my situation based on this form data.', formData)

      setStep(2)
      await generateScenarios(sessionId)

      setStep(3)
      await runAnalysis(sessionId)

      setStep(4)
      // Monte Carlo runs server-side as part of runAnalysis — nothing to call here

      setStep(5)
      const res = await getRankedScenarios(sessionId, 5)
      setRanked(res.ranked)
      setTotal(res.total)

      setPhase('results')
    } catch (e: any) {
      setError(e.message)
      setPhase('error')
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
            <span className="status-dot" />
            <span>Connecting to backend…</span>
          </div>
        )}

        {phase === 'error' && (
          <div className="status-card status-error">
            <span className="status-dot" />
            <span>{error ?? 'Backend unreachable'}</span>
          </div>
        )}

        {phase === 'idle' && (
          <div className="idle-view">
            <div className="status-card status-ok" style={{ marginBottom: '2rem' }}>
              <span className="status-dot" />
              <span>Backend connected</span>
            </div>
            <div className="hero-card card">
              <h2>Make your next big decision with clarity</h2>
              <p>Describe your situation, and we'll simulate multiple realistic paths — ranked by outcomes, backed by research and Monte Carlo analysis.</p>
              <button className="btn-primary" onClick={handleStart}>Get started →</button>
            </div>
          </div>
        )}

        {phase === 'intake' && (
          <IntakeForm onSubmit={handleIntakeSubmit} loading={false} />
        )}

        {phase === 'analyzing' && (
          <div className="analyzing-view card">
            <div className="analyzing-spinner" />
            <h3>Analyzing your decision…</h3>
            <div className="steps-list">
              {STEPS.map((s, i) => (
                <div key={i} className={`step-item ${i < step ? 'done' : i === step ? 'active' : 'pending'}`}>
                  <span className="step-icon">{i < step ? '✓' : i === step ? '⟳' : '○'}</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {phase === 'results' && (
          <ScenarioCards
            ranked={ranked}
            total={total}
            onShowMore={handleShowMore}
            showingAll={showingAll}
          />
        )}

      </main>
    </div>
  )
}

export default App
