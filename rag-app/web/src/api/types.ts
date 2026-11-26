export type ModelInfo = {
  role: 'embedding' | 'generation' | 'vision'
  name: string
  installed: boolean
  required: boolean
}

export type OllamaInfo = {
  reachable: boolean
  version: string | null
  base_url: string
  reason: string | null
  models: ModelInfo[]
}

export type IndexInfo = {
  records: number
  active: number
  embedded: number
  reused: number
  dim: number | null
  seconds: number
}

export type HealthResponse = {
  status: 'loading' | 'ready' | 'degraded' | 'error'
  mode: 'hybrid' | 'lexical' | null
  can_answer: boolean
  core_version: string
  api_version: string
  error: string | null
  ollama: OllamaInfo | null
  index: IndexInfo | null
}

export type NodeOut = {
  id: string
  name_fa: string
  name_en: string
  node_type: string
  layer: number
  parent_id: string | null
}

export type NodesResponse = {
  default_node_id: string
  nodes: NodeOut[]
}

export type AskRequest = {
  question: string
  node_id: string
  top_k?: number | null
}

export type CitationOut = {
  label: string
  valid: boolean
  granularity: string | null
  reason: string | null
}

export type SourceOut = {
  label: string
  key: string
  document_id: string
  title_fa: string
  title_en: string
  version: string
  language: string
  order: number
  heading_path: string[]
  page: number | null
  paragraph: number | null
  excerpt: string
  cited: boolean
}

export type EscalationOut = {
  target: string
  target_name_fa: string | null
  reason: string
}

export type AskResponse = {
  status:
    | 'answered'
    | 'insufficient_context'
    | 'not_found_in_scope'
    | 'out_of_scope'
  grounded: boolean
  text: string
  language: string
  node_id: string
  node_name_fa: string | null
  citations: CitationOut[]
  sources: SourceOut[]
  escalation: EscalationOut | null
  fact_flags: string[]
  model: string | null
  prompt_version: string | null
  timings_s: Record<string, number>
}

export type ErrorBody = {
  code: string
  message: string
}

export type ErrorResponse = {
  error: ErrorBody
}
