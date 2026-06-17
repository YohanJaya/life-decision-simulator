import { useEffect, useState } from 'react'
import { checkStatus } from './api'

function App() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'error'>('checking')

  useEffect(() => {
    checkStatus()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>Second Brain</h1>
        <p className="tagline">AI-powered life-decision simulator</p>
      </header>

      <main className="app-main">
        <div className={`status-card status-${status}`}>
          <span className="status-dot" />
          <span>
            Backend:{' '}
            <strong>
              {status === 'checking' ? 'connecting…' : status === 'ok' ? 'connected' : 'unreachable'}
            </strong>
          </span>
        </div>

        <div className="milestone-notice">
          <p>Milestone 1 complete — plumbing in place.</p>
          <p>Proceed to Milestone 2 to unlock the intake flow.</p>
        </div>
      </main>
    </div>
  )
}

export default App
