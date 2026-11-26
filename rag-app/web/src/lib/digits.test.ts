import { describe, expect, it } from 'vitest'
import { toLatinDigits, toPersianDigits } from './digits'

describe('toLatinDigits', () => {
  it('maps Persian digits to Latin', () => {
    expect(toLatinDigits('۰۱۲۳۴۵۶۷۸۹')).toBe('0123456789')
  })

  it('maps Arabic-Indic digits to Latin', () => {
    expect(toLatinDigits('٠١٢٣٤٥٦٧٨٩')).toBe('0123456789')
  })

  it('leaves Latin and non-digits unchanged', () => {
    expect(toLatinDigits('AR-FIN-۰۰۸ و x')).toBe('AR-FIN-008 و x')
    expect(toLatinDigits('')).toBe('')
  })
})

describe('toPersianDigits', () => {
  it('maps Latin digits to Persian', () => {
    expect(toPersianDigits('0123456789')).toBe('۰۱۲۳۴۵۶۷۸۹')
  })

  it('leaves non-Latin digits unchanged', () => {
    expect(toPersianDigits('AR-HR-005 §12')).toBe('AR-HR-۰۰۵ §۱۲')
    expect(toPersianDigits('')).toBe('')
  })
})
