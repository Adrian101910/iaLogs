export type Severity = 'TRACE' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

export interface LogEvent {
  id: string
  timestamp: string
  received_at: string
  source: string
  service: string | null
  severity: Severity
  message: string
  attributes: Record<string, unknown>
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Analysis {
  id: string
  created_at: string
  model: string
  prompt_version: string
  log_ids: string[]
  diagnosis: {
    summary: string
    findings: { description: string; log_ids: string[] }[]
    possible_causes: { description: string; log_ids: string[] }[]
    evidence: { log_id: string; explanation: string }[]
    next_checks: string[]
    missing_information: string[]
    uncertainty: 'low' | 'medium' | 'high'
  }
}
