import { useState, useEffect, useRef } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  messages: Message[]
  onSend: (text: string) => void
  onProceed: () => void
  onClarify: () => void
  loading: boolean
  profileComplete: boolean
}

export default function ChatView({ messages, onSend, onProceed, onClarify, loading, profileComplete }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, profileComplete])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    onSend(text)
    setInput('')
  }

  return (
    <div className="chat-view card">
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble chat-bubble-${m.role}`}>
            <span className="chat-role">{m.role === 'assistant' ? 'Advisor' : 'You'}</span>
            <p>{m.content}</p>
          </div>
        ))}
        {loading && (
          <div className="chat-bubble chat-bubble-assistant">
            <span className="chat-role">Advisor</span>
            <p className="chat-typing">Thinking<span className="dots">...</span></p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {!profileComplete && (
        <form className="chat-input-row" onSubmit={handleSubmit}>
          <input
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Type your reply…"
            disabled={loading}
            autoFocus
          />
          <button className="btn-send" type="submit" disabled={!input.trim() || loading}>
            Send
          </button>
        </form>
      )}

      {profileComplete && !loading && (
        <div className="profile-ready">
          <div className="profile-ready-badge">Profile complete</div>
          <p className="profile-ready-text">
            The advisor has gathered enough information. What would you like to do?
          </p>
          <div className="profile-ready-actions">
            <button className="btn-primary" onClick={onProceed}>
              Go to Analysis →
            </button>
            <button className="btn-clarify" onClick={onClarify}>
              Clarify More
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
