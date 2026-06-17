import { useState } from 'react'
import type { FormData } from '../types'

interface Props {
  onSubmit: (data: FormData) => void
  loading: boolean
}

export default function IntakeForm({ onSubmit, loading }: Props) {
  const [form, setForm] = useState<FormData>({
    name: '',
    current_situation: '',
    decision_domain: '',
    location: '',
    options_of_interest: [''],
  })

  function setField<K extends keyof FormData>(key: K, value: FormData[K]) {
    setForm(f => ({ ...f, [key]: value }))
  }

  function setOption(idx: number, value: string) {
    const opts = [...form.options_of_interest]
    opts[idx] = value
    setField('options_of_interest', opts)
  }

  function addOption() {
    setField('options_of_interest', [...form.options_of_interest, ''])
  }

  function removeOption(idx: number) {
    setField('options_of_interest', form.options_of_interest.filter((_, i) => i !== idx))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const cleaned = {
      ...form,
      options_of_interest: form.options_of_interest.filter(o => o.trim()),
    }
    onSubmit(cleaned)
  }

  const valid = form.name.trim() && form.current_situation.trim() &&
    form.decision_domain.trim() && form.location.trim() &&
    form.options_of_interest.some(o => o.trim())

  return (
    <form className="intake-form card" onSubmit={handleSubmit}>
      <h2 className="form-title">Tell us about your decision</h2>
      <p className="form-subtitle">We'll simulate multiple paths and rank them for you.</p>

      <div className="form-group">
        <label>Your name</label>
        <input
          value={form.name}
          onChange={e => setField('name', e.target.value)}
          placeholder="e.g. Alex"
        />
      </div>

      <div className="form-group">
        <label>Your current situation</label>
        <textarea
          value={form.current_situation}
          onChange={e => setField('current_situation', e.target.value)}
          placeholder="e.g. Final-year CS undergrad at XYZ University, GPA 3.7, interested in ML"
          rows={2}
        />
      </div>

      <div className="form-group">
        <label>What decision are you facing?</label>
        <input
          value={form.decision_domain}
          onChange={e => setField('decision_domain', e.target.value)}
          placeholder="e.g. Higher studies vs industry job vs startup"
        />
      </div>

      <div className="form-group">
        <label>Your current location</label>
        <input
          value={form.location}
          onChange={e => setField('location', e.target.value)}
          placeholder="e.g. Colombo, Sri Lanka"
        />
      </div>

      <div className="form-group">
        <label>Options you're already considering</label>
        {form.options_of_interest.map((opt, i) => (
          <div key={i} className="option-row">
            <input
              value={opt}
              onChange={e => setOption(i, e.target.value)}
              placeholder={`Option ${i + 1}, e.g. MS in US`}
            />
            {form.options_of_interest.length > 1 && (
              <button type="button" className="btn-remove" onClick={() => removeOption(i)}>✕</button>
            )}
          </div>
        ))}
        <button type="button" className="btn-add-option" onClick={addOption}>+ Add option</button>
      </div>

      <button type="submit" className="btn-primary" disabled={!valid || loading}>
        {loading ? 'Analyzing…' : 'Simulate my decision'}
      </button>
    </form>
  )
}
