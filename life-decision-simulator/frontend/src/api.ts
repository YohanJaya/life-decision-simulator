import type {
  FormData, UserProfile, Scenario, QuantResult, ResearchResult,
  MonteCarloResult, MarketOutlook, TradeoffMatrix,
  RankedScenariosResponse,
  WhatIfDiff, DecisionBrief,
} from './types'

const BASE = '/api'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function checkStatus(): Promise<string> {
  const res = await fetch('/')
  if (!res.ok) throw new Error('Backend unreachable')
  const data: { status: string } = await res.json()
  return data.status
}

export async function createSession(): Promise<string> {
  const data: { session_id: string } = await post('/session', {})
  return data.session_id
}

export async function sendIntake(
  sessionId: string,
  message: string,
  formData?: FormData,
): Promise<{ reply: string; profile_complete: boolean; profile?: UserProfile }> {
  return post('/intake', { session_id: sessionId, message, form_data: formData })
}

export async function generateScenarios(sessionId: string): Promise<{ scenarios: Scenario[] }> {
  return post('/scenarios/generate', { session_id: sessionId })
}

export async function runAnalysis(sessionId: string): Promise<{
  quant: QuantResult[]
  research: ResearchResult[]
  market_outlooks: MarketOutlook[]
  monte_carlo: MonteCarloResult[]
  tradeoffs: TradeoffMatrix
}> {
  return post('/analysis/run', { session_id: sessionId })
}

export async function getRankedScenarios(
  sessionId: string,
  limit: number = 5,
): Promise<RankedScenariosResponse> {
  return get(`/scenarios/ranked/${sessionId}?limit=${limit}`)
}

export async function submitWhatIf(
  sessionId: string,
  perturbation: string,
): Promise<{ diff: WhatIfDiff }> {
  return post('/whatif', { session_id: sessionId, perturbation })
}

export async function getBrief(sessionId: string): Promise<{ brief: DecisionBrief }> {
  return post('/brief', { session_id: sessionId })
}
