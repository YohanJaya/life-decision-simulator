import { useState } from 'react'
import type { RankedScenario, TradeoffScore } from '../types'

interface Props {
  ranked: RankedScenario[]
  total: number
  onShowMore: () => void
  showingAll: boolean
}

const SCORE_COLOR: Record<TradeoffScore, string> = {
  strong: 'var(--green)',
  mixed:  'var(--yellow)',
  weak:   'var(--red)',
  unclear:'var(--muted)',
}

const SCORE_LABEL: Record<TradeoffScore, string> = {
  strong:  '✓ Strong',
  mixed:   '~ Mixed',
  weak:    '✗ Weak',
  unclear: '? Unclear',
}

const RISK_COLOR = { low: 'var(--green)', medium: 'var(--yellow)', high: 'var(--red)' }

function fmt(n: number) {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000)     return `$${(n / 1_000).toFixed(0)}k`
  return `$${n.toFixed(0)}`
}

function pct(n: number) { return `${(n * 100).toFixed(0)}%` }

function DimensionRow({ entry }: { entry: { dimension: string; score: TradeoffScore; rationale: string } }) {
  return (
    <div className="dimension-row">
      <div className="dimension-name">{entry.dimension.replace(/_/g, ' ')}</div>
      <div className="dimension-score" style={{ color: SCORE_COLOR[entry.score] }}>
        {SCORE_LABEL[entry.score]}
      </div>
      <div className="dimension-rationale">{entry.rationale}</div>
    </div>
  )
}

function DetailPanel({ item }: { item: RankedScenario }) {
  const { scenario, tradeoff_entries, quant, monte_carlo: mc, market_outlook: mo, research } = item

  return (
    <div className="detail-panel">
      <h3 className="detail-title">#{item.rank} {scenario.name}</h3>
      <p className="detail-description">{scenario.description}</p>

      {scenario.assumptions.length > 0 && (
        <div className="detail-section">
          <h4>Key Assumptions</h4>
          <ul className="assumptions-list">
            {scenario.assumptions.map((a, i) => (
              <li key={i}><strong>{a.key}:</strong> {a.value}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Tradeoff reasoning */}
      <div className="detail-section">
        <h4>Tradeoff Analysis</h4>
        <div className="dimensions-grid">
          {tradeoff_entries.map((e, i) => <DimensionRow key={i} entry={e} />)}
        </div>
      </div>

      {/* Financials */}
      {quant && (
        <div className="detail-section">
          <h4>Financial Outlook</h4>
          <div className="fin-grid">
            <div className="fin-cell">
              <div className="fin-label">Starting Salary</div>
              <div className="fin-range">
                <span>{fmt(quant.starting_salary_p25.value_usd)}</span>
                <span className="fin-mid">{fmt(quant.starting_salary_p50.value_usd)}</span>
                <span>{fmt(quant.starting_salary_p75.value_usd)}</span>
              </div>
              <div className="fin-sublabel">p25 / p50 / p75</div>
            </div>
            <div className="fin-cell">
              <div className="fin-label">5-Year Net</div>
              <div className="fin-mid">{fmt(quant.five_year_cumulative_net.value_usd)}</div>
              <div className="fin-sublabel" style={{ color: `var(--badge-${quant.five_year_cumulative_net.confidence})` }}>
                {quant.five_year_cumulative_net.confidence} confidence
              </div>
            </div>
            {quant.debt_load.value_usd > 0 && (
              <div className="fin-cell">
                <div className="fin-label">Debt Load</div>
                <div className="fin-mid" style={{ color: 'var(--red)' }}>
                  {fmt(quant.debt_load.value_usd)}
                </div>
                {quant.break_even_years && (
                  <div className="fin-sublabel">Break-even: {fmt(quant.break_even_years.value_usd)}yr</div>
                )}
              </div>
            )}
          </div>
          {quant.notes.length > 0 && (
            <ul className="notes-list">
              {quant.notes.map((n, i) => <li key={i}>{n}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Monte Carlo */}
      {mc && (
        <div className="detail-section">
          <h4>
            Monte Carlo Distribution
            <span className="section-meta">{mc.n_simulations.toLocaleString()} simulations</span>
          </h4>
          <div className="mc-bar-wrap">
            <span className="mc-bar-label">p10</span>
            <div className="mc-bar">
              <div className="mc-range" />
            </div>
            <span className="mc-bar-label">p90</span>
          </div>
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
            <span>Probability of positive outcome: <strong style={{ color: 'var(--green)' }}>{pct(mc.prob_positive)}</strong></span>
            <span>Major disruption risk: <strong style={{ color: 'var(--yellow)' }}>{pct(mc.prob_major_disruption)}</strong></span>
            <span>Risk: <strong style={{ color: RISK_COLOR[mc.risk_label] }}>{mc.risk_label}</strong></span>
          </div>
        </div>
      )}

      {/* Market outlook */}
      {mo && (
        <div className="detail-section">
          <h4>Future Market Outlook</h4>
          <div className="outlook-row">
            <div className="outlook-cell">
              <div className="outlook-label">Job Growth</div>
              <div className="outlook-val">{mo.projected_growth.replace(/_/g, ' ')}</div>
              <div className="outlook-rationale">{mo.projected_growth_rationale}</div>
            </div>
            <div className="outlook-cell">
              <div className="outlook-label">Automation Risk</div>
              <div className="outlook-val" style={{ color: RISK_COLOR[mo.automation_risk] }}>
                {mo.automation_risk}
              </div>
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

      {/* Research sources */}
      {research && research.bullets.length > 0 && (
        <div className="detail-section">
          <h4>Research & Sources</h4>
          <ul className="research-list">
            {research.bullets.map((b, i) => (
              <li key={i}>
                <span>{b.text}</span>
                {b.source_url && (
                  <a href={b.source_url} target="_blank" rel="noopener noreferrer" className="source-link">
                    Source ↗
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function ScenarioCards({ ranked, total, onShowMore, showingAll }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(ranked[0]?.scenario.id ?? null)
  const selected = ranked.find(r => r.scenario.id === selectedId) ?? null

  return (
    <div className="scenarios-layout">
      {/* Left: ranked list */}
      <div className="scenario-list">
        <div className="list-header">
          <h2>Ranked Scenarios</h2>
          <span className="list-meta">{ranked.length} of {total}</span>
        </div>

        {ranked.map(item => {
          const isSelected = item.scenario.id === selectedId
          const strong = item.tradeoff_entries.filter(e => e.score === 'strong').length
          const weak   = item.tradeoff_entries.filter(e => e.score === 'weak').length

          return (
            <button
              key={item.scenario.id}
              className={`scenario-card ${isSelected ? 'selected' : ''}`}
              onClick={() => setSelectedId(item.scenario.id)}
            >
              <div className="card-top-row">
                <span className="rank-badge">#{item.rank}</span>
                <span className="scenario-name">{item.scenario.name}</span>
                {item.monte_carlo && (
                  <span className="risk-chip" style={{ color: RISK_COLOR[item.monte_carlo.risk_label] }}>
                    {item.monte_carlo.risk_label} risk
                  </span>
                )}
              </div>
              <div className="card-score-bar">
                <div className="score-fill" style={{ width: `${Math.min((item.score / 30) * 100, 100)}%` }} />
              </div>
              <div className="card-summary">
                <span style={{ color: 'var(--green)' }}>{strong} strong</span>
                <span style={{ color: 'var(--red)' }}>{weak} weak</span>
                {item.monte_carlo && (
                  <span style={{ color: 'var(--accent)' }}>
                    {pct(item.monte_carlo.prob_positive)} positive
                  </span>
                )}
              </div>
            </button>
          )
        })}

        {!showingAll && ranked.length < total && (
          <button className="btn-show-more" onClick={onShowMore}>
            Show {total - ranked.length} more scenarios ↓
          </button>
        )}
      </div>

      {/* Right: detail panel */}
      <div className="detail-column">
        {selected
          ? <DetailPanel item={selected} />
          : <div className="detail-empty">Select a scenario to see details</div>
        }
      </div>
    </div>
  )
}
