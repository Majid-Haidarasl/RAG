import { describe, expect, it } from 'vitest'
import { formatCitationLabel, splitCitations } from './citations'

describe('formatCitationLabel', () => {
  it('replaces section sign with Persian بند', () => {
    expect(formatCitationLabel('AR-HR-006 §9')).toBe('AR-HR-006 · بند ۹')
    expect(formatCitationLabel('AR-HR-005 §12/fa')).toBe(
      'AR-HR-005 · بند ۱۲/fa',
    )
    expect(formatCitationLabel('AR-FIN-010')).toBe('AR-FIN-010')
  })
})

describe('splitCitations', () => {
  it('splits two separate brackets into text and cite segments', () => {
    expect(
      splitCitations('شروع [AR-HR-005 §12] میانه [AR-FIN-010] پایان'),
    ).toEqual([
      { kind: 'text', text: 'شروع ' },
      { kind: 'cite', label: 'AR-HR-005 §12', raw: 'AR-HR-005 §12' },
      { kind: 'text', text: ' میانه ' },
      { kind: 'cite', label: 'AR-FIN-010', raw: 'AR-FIN-010' },
      { kind: 'text', text: ' پایان' },
    ])
  })

  it('emits one cite per source inside a multi-ref bracket', () => {
    expect(
      splitCitations('x [AR-HR-005 §1; AR-HR-004 §3، AR-SW-022 §2] y'),
    ).toEqual([
      { kind: 'text', text: 'x ' },
      { kind: 'cite', label: 'AR-HR-005 §1', raw: 'AR-HR-005 §1' },
      { kind: 'cite', label: 'AR-HR-004 §3', raw: 'AR-HR-004 §3' },
      { kind: 'cite', label: 'AR-SW-022 §2', raw: 'AR-SW-022 §2' },
      { kind: 'text', text: ' y' },
    ])
  })

  it('normalises Persian digits in document id and section', () => {
    expect(splitCitations('[AR-SW-۰۲۲ § ۱۲]')).toEqual([
      { kind: 'cite', label: 'AR-SW-022 §12', raw: 'AR-SW-022 § 12' },
    ])
  })

  it('keeps non-document brackets as text', () => {
    expect(splitCitations('نکته [یادداشت] اینجا')).toEqual([
      { kind: 'text', text: 'نکته [یادداشت] اینجا' },
    ])
  })
})
