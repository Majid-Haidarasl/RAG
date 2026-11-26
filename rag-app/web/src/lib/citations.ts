import { toLatinDigits } from './digits'

export type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'cite'; label: string; raw: string }

/** Matches rag_core.qa.domain.citations bracket finder. */
const BRACKET_RE = /\[([^\[\]]{3,200})\]/g

/**
 * Document + optional section / chunk id + optional language.
 * Same shape as rag_core `_REF_RE` (after digit normalization).
 */
const REF_RE =
  /(AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?)(?:\s*(?:§\s*(\d+)|#c(\d+))(?:\s*\/\s*(fa|en))?)?/i

const DOC_RE = /AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?/i

const SPLIT_RE = /[;,،؛]/

function labelFor(part: string): { label: string; raw: string } | null {
  const raw = part.trim()
  if (!raw) return null
  const m = raw.match(REF_RE)
  if (!m) return null
  const documentId = m[1].toUpperCase()
  const sec = m[2] ?? m[3]
  const language = (m[4] ?? '').toLowerCase() || null
  const order = sec != null ? Number.parseInt(sec, 10) : null
  const base = order == null ? documentId : `${documentId} §${order}`
  const label = language ? `${base}/${language}` : base
  return { label, raw }
}

/**
 * Split answer text into plain text and citation chips.
 * Brackets without a document id (e.g. `[یادداشت]`) stay as text.
 * Labels match rag_core (`AR-HR-005 §12`, optional `/fa`|`/en`).
 */
export function splitCitations(text: string): Segment[] {
  const input = text ?? ''
  if (!input) return []

  const segments: Segment[] = []
  let last = 0

  for (const match of input.matchAll(BRACKET_RE)) {
    const full = match[0]
    const inner = match[1]
    const index = match.index ?? 0
    const normalized = toLatinDigits(inner)

    if (!DOC_RE.test(normalized)) {
      continue
    }

    if (index > last) {
      segments.push({ kind: 'text', text: input.slice(last, index) })
    }

    for (const part of normalized.split(SPLIT_RE)) {
      const cite = labelFor(part)
      if (cite) {
        segments.push({ kind: 'cite', label: cite.label, raw: cite.raw })
      }
    }

    last = index + full.length
  }

  if (last < input.length) {
    segments.push({ kind: 'text', text: input.slice(last) })
  } else if (segments.length === 0) {
    segments.push({ kind: 'text', text: input })
  }

  return segments
}
