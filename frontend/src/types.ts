// Mirrors backend app/schemas.py — keep in sync

export interface FormData {
  name: string
  current_situation: string
  decision_domain: string
  location: string
  options_of_interest: string[]
}

export interface UserProfile {
  name: string
  current_situation: string
  decision_domain: string
  location: string
  stated_values: string[]
  hard_constraints: string[]
  soft_preferences: string[]
  options_of_interest: string[]
  risk_tolerance: 'low' | 'medium' | 'high'
  time_horizon_years: number
  additional_context: string
}

export interface Assumption {
  key: string
  value: string
}

export interface Scenario {
  id: string
  name: string
  description: string
  assumptions: Assumption[]
}

export interface FinancialProjection {
  label: string
  value_usd: number
  confidence: 'high' | 'medium' | 'low'
  source_rows: string[]
}

export interface QuantResult {
  scenario_id: string
  starting_salary_p25: FinancialProjection
  starting_salary_p50: FinancialProjection
  starting_salary_p75: FinancialProjection
  five_year_cumulative_net: FinancialProjection
  debt_load: FinancialProjection
  break_even_years: FinancialProjection | null
  notes: string[]
}

export interface ResearchBullet {
  text: string
  source_url: string
}

export interface ResearchResult {
  scenario_id: string
  bullets: ResearchBullet[]
  search_queries_used: string[]
}

export type TradeoffScore = 'strong' | 'mixed' | 'weak' | 'unclear'

export interface TradeoffEntry {
  scenario_id: string
  dimension: string
  score: TradeoffScore
  rationale: string
}

export interface TradeoffMatrix {
  entries: TradeoffEntry[]
  named_tradeoffs: string[]
}

export interface YearlyDistribution {
  year: number
  p10: number
  p25: number
  p50: number
  p75: number
  p90: number
}

export interface MonteCarloResult {
  scenario_id: string
  n_simulations: number
  cumulative_net_p10: number
  cumulative_net_p25: number
  cumulative_net_p50: number
  cumulative_net_p75: number
  cumulative_net_p90: number
  prob_positive: number
  prob_major_disruption: number
  downside_risk_usd: number
  upside_potential_usd: number
  yearly: YearlyDistribution[]
  risk_label: 'low' | 'medium' | 'high'
}

export interface MarketOutlook {
  scenario_id: string
  target_role: string
  region: string
  projected_growth: 'much_faster' | 'faster' | 'average' | 'slower' | 'declining' | 'uncertain'
  projected_growth_rationale: string
  automation_risk: 'low' | 'medium' | 'high'
  automation_risk_rationale: string
  demand_trend: 'growing' | 'stable' | 'declining' | 'uncertain'
  key_risks: string[]
  key_tailwinds: string[]
  time_horizon_fit: 'strong' | 'mixed' | 'weak'
  time_horizon_rationale: string
  sources: string[]
}

export interface RankedScenario {
  rank: number
  score: number
  scenario: Scenario
  tradeoff_entries: TradeoffEntry[]
  research: ResearchResult | null
  quant: QuantResult | null
  monte_carlo: MonteCarloResult | null
  market_outlook: MarketOutlook | null
}

export interface RankedScenariosResponse {
  ranked: RankedScenario[]
  total: number
}

export interface QuantChange {
  scenario_id: string
  field: string
  before_usd: number
  after_usd: number
  delta_usd: number
}

export interface TradeoffChange {
  scenario_id: string
  dimension: string
  before_score: TradeoffScore
  after_score: TradeoffScore
  rationale: string
}

export interface WhatIfDiff {
  perturbation: string
  affected_scenario_ids: string[]
  quant_changes: QuantChange[]
  tradeoff_changes: TradeoffChange[]
}

export interface DecisionBrief {
  session_id: string
  scenarios: Scenario[]
  tradeoff_matrix: TradeoffMatrix
  named_tradeoffs: string[]
  uncertainties: string[]
  user_questions: [string, string, string]
  generated_at: string
}
