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
  user_questions: [string, string, string]   // exactly 3
  generated_at: string
}
