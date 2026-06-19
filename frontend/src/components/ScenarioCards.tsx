import { useState } from 'react'
import type { RankedScenario, TradeoffScore } from '../types'
import MonteCarloChart from './MonteCarloChart'

interface Props {
  ranked: RankedScenario[]
  total: number
  onShowMore: () => void
  showingAll: boolean
}

type ResultsView = 'list' | 'detail' | 'compare'

const SCORE_COLOR: Record<TradeoffScore, string> = {
  strong:  'var(--green)',
  mixed:   'var(--yellow)',
  weak:    'var(--red)',
  unclear: 'var(--muted)',
}
const SCORE_LABEL: Record<TradeoffScore, string> = {
  strong:  '✓ Strong',
  mixed:   '~ Mixed',
  weak:    '✗ Weak',
  unclear: '? Unclear',
}
const RISK_COLOR = { low: 'var(--green)', medium: 'var(--yellow)', high: 'var(--red)' }
const RANK_CLASS: Record<number, string> = { 1: 'gold', 2: 'silver', 3: 'bronze' }
const RANK_ICON: Record<number, string>  = { 1: '🥇', 2: '🥈', 3: '🥉' }

function fmt(n: number) {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000)     return `$${(n / 1_000).toFixed(0)}k`
  return `$${n.toFixed(0)}`
}
function pct(n: number) { return `${(n * 100).toFixed(0)}%` }

// ── List card ──────────────────────────────────────────────────────────────────
function ScenarioListCard({ item, onClick, delay }: {
  item: RankedScenario
  onClick: () => void
  delay: number
}) {
  const strong = item.tradeoff_entries.filter(e => e.score === 'strong').length
  const weak   = item.tradeoff_entries.filter(e => e.score === 'weak').length
  const mc = item.monte_carlo
  const q  = item.quant

  return (
    <button
      className={`result-card ${RANK_CLASS[item.rank] ?? ''}`}
      style={{ animationDelay: `${delay}s` }}
      onClick={onClick}
    >
      <div className="result-card-header">
        <span className={`rank-badge ${RANK_CLASS[item.rank] ?? ''}`}>
          {RANK_ICON[item.rank] ?? `#${item.rank}`}
        </span>
        <span className="result-card-name">{item.scenario.name}</span>
        {mc && (
          <span className="risk-chip" style={{ color: RISK_COLOR[mc.risk_label] }}>
            {mc.risk_label} risk
          </span>
        )}
      </div>

      <p className="result-card-desc">{item.scenario.description}</p>

      <div className="result-card-score-bar">
        <div className="score-fill" style={{ width: `${Math.min((item.score / 30) * 100, 100)}%` }} />
      </div>

      <div className="result-card-stats">
        {q && (
          <>
            <div className="stat-pill">
              <span className="stat-label">Salary p50</span>
              <span className="stat-val">{fmt(q.starting_salary_p50.value_usd)}</span>
            </div>
            <div className="stat-pill">
              <span className="stat-label">5-yr net</span>
              <span className="stat-val">{fmt(q.five_year_cumulative_net.value_usd)}</span>
            </div>
          </>
        )}
        {mc && (
          <div className="stat-pill">
            <span className="stat-label">Prob positive</span>
            <span className="stat-val" style={{ color: 'var(--green)' }}>{pct(mc.prob_positive)}</span>
          </div>
        )}
        <div className="stat-pill">
          <span className="stat-label">Tradeoffs</span>
          <span className="stat-val">
            <span style={{ color: 'var(--green)' }}>{strong}✓</span>
            {' / '}
            <span style={{ color: 'var(--red)' }}>{weak}✗</span>
          </span>
        </div>
      </div>

      <div className="result-card-cta">View full analysis →</div>
    </button>
  )
}

// ── Detail view ────────────────────────────────────────────────────────────────
function DetailView({ item, onBack }: { item: RankedScenario; onBack: () => void }) {
  const { scenario, tradeoff_entries, quant: q, monte_carlo: mc, market_outlook: mo, research } = item

  return (
    <div className="detail-page">
      <div className="detail-page-nav">
        <button className="btn-back" onClick={onBack}>← Back to results</button>
        <span className={`rank-badge ${RANK_CLASS[item.rank] ?? ''}`} style={{ fontSize: '0.85rem', padding: '0.25em 0.75em' }}>
          {RANK_ICON[item.rank] ?? `#${item.rank}`} Rank #{item.rank}
        </span>
      </div>

      <h2 className="detail-page-title">{scenario.name}</h2>
      <p className="detail-page-desc">{scenario.description}</p>

      {scenario.assumptions.length > 0 && (
        <div className="detail-section">
          <h4><span className="section-icon">📌</span> Key Assumptions</h4>
          <ul className="assumptions-list">
            {scenario.assumptions.map((a, i) => (
              <li key={i}><strong>{a.key}:</strong> {a.value}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="detail-section">
        <h4><span className="section-icon">⚖️</span> Tradeoff Analysis</h4>
        <div className="dimensions-grid">
          {tradeoff_entries.map((e, i) => (
            <div className="dimension-row" key={i}>
              <div className="dimension-name">{e.dimension.replace(/_/g, ' ')}</div>
              <div className="dimension-score" style={{ color: SCORE_COLOR[e.score] }}>{SCORE_LABEL[e.score]}</div>
              <div className="dimension-rationale">{e.rationale}</div>
            </div>
          ))}
        </div>
      </div>

      {q && (
        <div className="detail-section">
          <h4><span className="section-icon">💰</span> Financial Outlook</h4>
          <div className="fin-grid">
            <div className="fin-cell">
              <div className="fin-label">Starting Salary</div>
              <div className="fin-range">
                <span>{fmt(q.starting_salary_p25.value_usd)}</span>
                <span className="fin-mid">{fmt(q.starting_salary_p50.value_usd)}</span>
                <span>{fmt(q.starting_salary_p75.value_usd)}</span>
              </div>
              <div className="fin-sublabel">p25 / p50 / p75</div>
            </div>
            <div className="fin-cell">
              <div className="fin-label">5-Year Net</div>
              <div className="fin-mid">{fmt(q.five_year_cumulative_net.value_usd)}</div>
              <div className="fin-sublabel" style={{ color: q.five_year_cumulative_net.confidence === 'high' ? 'var(--green)' : 'var(--yellow)' }}>
                {q.five_year_cumulative_net.confidence} confidence
              </div>
            </div>
            {q.debt_load.value_usd > 0 && (
              <div className="fin-cell">
                <div className="fin-label">Debt Load</div>
                <div className="fin-mid" style={{ color: 'var(--red)' }}>{fmt(q.debt_load.value_usd)}</div>
              </div>
            )}
          </div>
          {q.notes.length > 0 && (
            <ul className="notes-list">{q.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          )}
        </div>
      )}

      {mc && (
        <div className="detail-section">
          <h4>
            <span className="section-icon">🎲</span> Monte Carlo Distribution
            <span className="section-meta">{mc.n_simulations.toLocaleString()} simulations</span>
          </h4>
          <MonteCarloChart mc={mc} />
          <div className="mc-stats">
            <div className="mc-stat">
              <span className="mc-stat-val" style={{ color: 'var(--red)' }}>{fmt(mc.cumulative_net_p10)}</span>
              <span className="mc-stat-lbl">Bad case (p10)</span>
            </div>
            <div className="mc-stat">
              <span className="mc-stat-val">{fmt(mc.cumulative_net_p50)}</span>
              <span className="mc-stat-lbl">Median (p50)</span>
            </div>
            <div className="mc-stat">
              <span className="mc-stat-val" style={{ color: 'var(--green)' }}>{fmt(mc.cumulative_net_p90)}</span>
              <span className="mc-stat-lbl">Good case (p90)</span>
            </div>
          </div>
          <div className="mc-meta-row">
            <span>Positive outcome: <strong style={{ color: 'var(--green)' }}>{pct(mc.prob_positive)}</strong></span>
            <span>Disruption risk: <strong style={{ color: 'var(--yellow)' }}>{pct(mc.prob_major_disruption)}</strong></span>
            <span>Risk: <strong style={{ color: RISK_COLOR[mc.risk_label] }}>{mc.risk_label}</strong></span>
          </div>
        </div>
      )}

      {mo && (
        <div className="detail-section">
          <h4><span className="section-icon">📈</span> Future Market Outlook</h4>
          <div className="outlook-row">
            <div className="outlook-cell">
              <div className="outlook-label">Job Growth</div>
              <div className="outlook-val">{mo.projected_growth.replace(/_/g, ' ')}</div>
              <div className="outlook-rationale">{mo.projected_growth_rationale}</div>
            </div>
            <div className="outlook-cell">
              <div className="outlook-label">Automation Risk</div>
              <div className="outlook-val" style={{ color: RISK_COLOR[mo.automation_risk] }}>{mo.automation_risk}</div>
              <div className="outlook-rationale">{mo.automation_risk_rationale}</div>
            </div>
            <div className="outlook-cell">
              <div className="outlook-label">Demand Trend</div>
              <div className="outlook-val">{mo.demand_trend}</div>
              <div className="outlook-rationale">{mo.time_horizon_rationale}</div>
            </div>
          </div>
          <div className="risks-tailwinds">
            <div>
              <div className="rt-label" style={{ color: 'var(--red)' }}>Risks</div>
              <ul>{mo.key_risks.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
            <div>
              <div className="rt-label" style={{ color: 'var(--green)' }}>Tailwinds</div>
              <ul>{mo.key_tailwinds.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </div>
          </div>
        </div>
      )}

      {research && research.bullets.length > 0 && (
        <div className="detail-section">
          <h4><span className="section-icon">🔍</span> Research & Sources</h4>
          <ul className="research-list">
            {research.bullets.map((b, i) => (
              <li key={i}>
                <span>{b.text}</span>
                {b.source_url && (
                  <a href={b.source_url} target="_blank" rel="noopener noreferrer" className="source-link">Source ↗</a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Compare view ───────────────────────────────────────────────────────────────
function CompareView({ ranked, onBack }: { ranked: RankedScenario[]; onBack: () => void }) {
  const dims = ranked[0]?.tradeoff_entries.map(e => e.dimension) ?? []

  return (
    <div className="compare-page">
      <div className="detail-page-nav">
        <button className="btn-back" onClick={onBack}>← Back to results</button>
        <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>Comparing {ranked.length} scenarios</span>
      </div>

      <h2 className="detail-page-title">Scenario Comparison</h2>
      <p style={{ color: 'var(--muted)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        Side-by-side summary of all scenarios to help you make the final call.
      </p>

      <div className="compare-table-wrap">
        <table className="compare-table">
          <thead>
            <tr>
              <th className="compare-metric-col">Metric</th>
              {ranked.map(r => (
                <th key={r.scenario.id} className={`compare-scenario-col`}>
                  <div className={`rank-badge ${RANK_CLASS[r.rank] ?? ''}`} style={{ display: 'inline-block', marginBottom: '0.35rem' }}>
                    {RANK_ICON[r.rank] ?? `#${r.rank}`}
                  </div>
                  <div className="compare-scenario-name">{r.scenario.name}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="compare-group-row"><td colSpan={ranked.length + 1}>💰 Financials</td></tr>
            <tr>
              <td className="compare-metric">Salary (p50)</td>
              {ranked.map(r => <td key={r.scenario.id} className="compare-val">{r.quant ? fmt(r.quant.starting_salary_p50.value_usd) : '—'}</td>)}
            </tr>
            <tr>
              <td className="compare-metric">5-Year Net</td>
              {ranked.map(r => <td key={r.scenario.id} className="compare-val">{r.quant ? fmt(r.quant.five_year_cumulative_net.value_usd) : '—'}</td>)}
            </tr>
            <tr>
              <td className="compare-metric">Debt</td>
              {ranked.map(r => (
                <td key={r.scenario.id} className="compare-val" style={{ color: r.quant && r.quant.debt_load.value_usd > 0 ? 'var(--red)' : 'var(--green)' }}>
                  {r.quant ? (r.quant.debt_load.value_usd > 0 ? fmt(r.quant.debt_load.value_usd) : 'None') : '—'}
                </td>
              ))}
            </tr>

            <tr className="compare-group-row"><td colSpan={ranked.length + 1}>🎲 Risk & Probability</td></tr>
            <tr>
              <td className="compare-metric">Prob. Positive</td>
              {ranked.map(r => <td key={r.scenario.id} className="compare-val" style={{ color: 'var(--green)' }}>{r.monte_carlo ? pct(r.monte_carlo.prob_positive) : '—'}</td>)}
            </tr>
            <tr>
              <td className="compare-metric">Risk Level</td>
              {ranked.map(r => (
                <td key={r.scenario.id} className="compare-val" style={{ color: r.monte_carlo ? RISK_COLOR[r.monte_carlo.risk_label] : 'var(--muted)', fontWeight: 700 }}>
                  {r.monte_carlo?.risk_label ?? '—'}
                </td>
              ))}
            </tr>

            <tr className="compare-group-row"><td colSpan={ranked.length + 1}>📈 Market Signals</td></tr>
            <tr>
              <td className="compare-metric">Job Growth</td>
              {ranked.map(r => <td key={r.scenario.id} className="compare-val">{r.market_outlook?.projected_growth.replace(/_/g,' ') ?? '—'}</td>)}
            </tr>
            <tr>
              <td className="compare-metric">Automation Risk</td>
              {ranked.map(r => (
                <td key={r.scenario.id} className="compare-val" style={{ color: r.market_outlook ? RISK_COLOR[r.market_outlook.automation_risk] : 'var(--muted)' }}>
                  {r.market_outlook?.automation_risk ?? '—'}
                </td>
              ))}
            </tr>

            <tr className="compare-group-row"><td colSpan={ranked.length + 1}>⚖️ Tradeoffs</td></tr>
            {dims.map(dim => (
              <tr key={dim}>
                <td className="compare-metric">{dim.replace(/_/g, ' ')}</td>
                {ranked.map(r => {
                  const entry = r.tradeoff_entries.find(e => e.dimension === dim)
                  return (
                    <td key={r.scenario.id} className="compare-val" style={{ color: entry ? SCORE_COLOR[entry.score] : 'var(--muted)', fontWeight: 600, fontSize: '0.8rem' }}>
                      {entry ? SCORE_LABEL[entry.score] : '—'}
                    </td>
                  )
                })}
              </tr>
            ))}

            <tr className="compare-group-row"><td colSpan={ranked.length + 1}>🏆 Overall</td></tr>
            <tr>
              <td className="compare-metric">Composite Score</td>
              {ranked.map(r => (
                <td key={r.scenario.id} className="compare-val" style={{ fontWeight: 700, color: 'var(--accent)' }}>
                  {r.score.toFixed(1)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────────────────────
export default function ScenarioCards({ ranked, total, onShowMore, showingAll }: Props) {
  const [view, setView]             = useState<ResultsView>('list')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selectedItem = ranked.find(r => r.scenario.id === selectedId) ?? null

  function openDetail(id: string) {
    setSelectedId(id)
    setView('detail')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function goBack() {
    setView('list')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (view === 'detail' && selectedItem) {
    return <DetailView item={selectedItem} onBack={goBack} />
  }

  if (view === 'compare') {
    return <CompareView ranked={ranked} onBack={goBack} />
  }

  return (
    <div className="results-page">
      <div className="results-page-header">
        <div>
          <h2 className="results-page-title">Your Ranked Scenarios</h2>
          <p className="results-page-sub">{ranked.length} paths analysed · click any to see full breakdown</p>
        </div>
        <button className="btn-compare" onClick={() => setView('compare')}>⚖️ Compare all</button>
      </div>

      <div className="results-grid">
        {ranked.map((item, idx) => (
          <ScenarioListCard
            key={item.scenario.id}
            item={item}
            onClick={() => openDetail(item.scenario.id)}
            delay={idx * 0.08}
          />
        ))}
      </div>

      {!showingAll && ranked.length < total && (
        <button className="btn-show-more" style={{ marginTop: '1rem' }} onClick={onShowMore}>
          Show {total - ranked.length} more scenarios ↓
        </button>
      )}
    </div>
  )
}
