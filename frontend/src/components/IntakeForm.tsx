import { useState } from 'react'
import type { FormData } from '../types'

interface Props {
  onSubmit: (data: FormData) => void
  loading: boolean
}

export default function IntakeForm({ onSubmit, loading }: Props) {
  const [form, setForm] = useState<FormData>({
    name: '',
    age: 22,
    degree_program: '',
    current_university: '',
    cgpa: 0,
    other_qualifications: [''],
    other_degrees_diplomas: [''],
    decision_domain: '',
    location: '',
    options_of_interest: [''],
  })

  function setField<K extends keyof FormData>(key: K, value: FormData[K]) {
    setForm(f => ({ ...f, [key]: value }))
  }

  function setListItem(field: 'options_of_interest' | 'other_qualifications' | 'other_degrees_diplomas', idx: number, value: string) {
    const arr = [...(form[field] as string[])]
    arr[idx] = value
    setField(field, arr as any)
  }

  function addListItem(field: 'options_of_interest' | 'other_qualifications' | 'other_degrees_diplomas') {
    setField(field, [...(form[field] as string[]), ''] as any)
  }

  function removeListItem(field: 'options_of_interest' | 'other_qualifications' | 'other_degrees_diplomas', idx: number) {
    setField(field, (form[field] as string[]).filter((_, i) => i !== idx) as any)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({
      ...form,
      other_qualifications: form.other_qualifications.filter(s => s.trim()),
      other_degrees_diplomas: form.other_degrees_diplomas.filter(s => s.trim()),
      options_of_interest: form.options_of_interest.filter(s => s.trim()),
    })
  }

  const valid =
    form.name.trim() &&
    form.degree_program.trim() &&
    form.current_university.trim() &&
    form.decision_domain.trim() &&
    form.location.trim() &&
    form.options_of_interest.some(o => o.trim())

  return (
    <form className="intake-form card" onSubmit={handleSubmit}>
      <div className="form-step-indicator">
        <span>📋</span> Step 1 of 2 — Fill in your profile, then chat with our AI advisor
      </div>
      <h2 className="form-title">Tell us about yourself</h2>
      <p className="form-subtitle">We'll have a short conversation to understand your goals, then simulate your best paths.</p>

      <div className="form-section-label"><span className="section-icon">👤</span> Personal Info</div>

      <div className="form-row">
        <div className="form-group">
          <label>Your name</label>
          <input
            value={form.name}
            onChange={e => setField('name', e.target.value)}
            placeholder="e.g. Kavindu"
          />
        </div>
        <div className="form-group form-group--small">
          <label>Age</label>
          <input
            type="number"
            min={17} max={35}
            value={form.age}
            onChange={e => setField('age', parseInt(e.target.value) || 22)}
          />
        </div>
      </div>

      <div className="form-group">
        <label>Degree program</label>
        <input
          value={form.degree_program}
          onChange={e => setField('degree_program', e.target.value)}
          placeholder="e.g. BSc (Hons) Computer Science"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Current university</label>
          <input
            value={form.current_university}
            onChange={e => setField('current_university', e.target.value)}
            placeholder="e.g. University of Moratuwa"
          />
        </div>
        <div className="form-group form-group--small">
          <label>CGPA</label>
          <input
            type="number"
            step="0.01" min={0} max={4}
            value={form.cgpa || ''}
            onChange={e => setField('cgpa', parseFloat(e.target.value) || 0)}
            placeholder="e.g. 3.65"
          />
        </div>
      </div>

      <div className="form-section-label"><span className="section-icon">🎓</span> Qualifications</div>

      <div className="form-group">
        <label>Other degrees or diplomas <span className="label-optional">(optional)</span></label>
        {form.other_degrees_diplomas.map((val, i) => (
          <div key={i} className="option-row">
            <input
              value={val}
              onChange={e => setListItem('other_degrees_diplomas', i, e.target.value)}
              placeholder="e.g. HND in Software Engineering"
            />
            {form.other_degrees_diplomas.length > 1 && (
              <button type="button" className="btn-remove" onClick={() => removeListItem('other_degrees_diplomas', i)}>✕</button>
            )}
          </div>
        ))}
        <button type="button" className="btn-add-option" onClick={() => addListItem('other_degrees_diplomas')}>+ Add</button>
      </div>

      <div className="form-group">
        <label>Other qualifications <span className="label-optional">(certifications, awards — optional)</span></label>
        {form.other_qualifications.map((val, i) => (
          <div key={i} className="option-row">
            <input
              value={val}
              onChange={e => setListItem('other_qualifications', i, e.target.value)}
              placeholder="e.g. AWS Solutions Architect, Dean's List"
            />
            {form.other_qualifications.length > 1 && (
              <button type="button" className="btn-remove" onClick={() => removeListItem('other_qualifications', i)}>✕</button>
            )}
          </div>
        ))}
        <button type="button" className="btn-add-option" onClick={() => addListItem('other_qualifications')}>+ Add</button>
      </div>

      <div className="form-section-label"><span className="section-icon">🎯</span> Your Decision</div>

      <div className="form-group">
        <label>What decision are you facing?</label>
        <input
          value={form.decision_domain}
          onChange={e => setField('decision_domain', e.target.value)}
          placeholder="e.g. Pursue MS abroad vs take a local job vs start a business"
        />
      </div>

      <div className="form-group">
        <label>Current location</label>
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
              onChange={e => setListItem('options_of_interest', i, e.target.value)}
              placeholder={`Option ${i + 1}, e.g. MS in US`}
            />
            {form.options_of_interest.length > 1 && (
              <button type="button" className="btn-remove" onClick={() => removeListItem('options_of_interest', i)}>✕</button>
            )}
          </div>
        ))}
        <button type="button" className="btn-add-option" onClick={() => addListItem('options_of_interest')}>+ Add option</button>
      </div>

      <button type="submit" className="btn-primary" disabled={!valid || loading}>
        {loading ? 'Starting conversation…' : 'Start →'}
      </button>
    </form>
  )
}
