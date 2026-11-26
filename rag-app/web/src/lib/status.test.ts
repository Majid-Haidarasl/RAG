import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { errorMessage, statusView } from './status'

describe('statusView', () => {
  it('maps answered + grounded', () => {
    expect(statusView('answered', true)).toEqual({
      label: 'پاسخ مستند',
      color: 'success',
      icon: 'ok',
    })
  })

  it('maps answered + not grounded', () => {
    expect(statusView('answered', false)).toEqual({
      label: 'پاسخ بدون ارجاع معتبر',
      color: 'warning',
      icon: 'warn',
    })
  })

  it('maps abstain and escalation statuses', () => {
    expect(statusView('insufficient_context', false)).toEqual({
      label: 'شواهد کافی نیست',
      color: 'warning',
      icon: 'warn',
    })
    expect(statusView('not_found_in_scope', false)).toEqual({
      label: 'در دامنهٔ این واحد پیدا نشد',
      color: 'default',
      icon: 'none',
    })
    expect(statusView('out_of_scope', false)).toEqual({
      label: 'خارج از دامنه، ارجاع به واحد دیگر',
      color: 'info',
      icon: 'route',
    })
  })
})

describe('errorMessage', () => {
  it('returns Persian copy for known codes', () => {
    expect(errorMessage(new ApiError(503, 'warming_up', 'x'))).toBe(
      'سیستم در حال آماده‌سازی است؛ چند لحظه بعد دوباره بپرسید',
    )
    expect(errorMessage(new ApiError(500, 'startup_failed', 'x'))).toBe(
      'راه‌اندازی سرور ناموفق بود',
    )
    expect(errorMessage(new ApiError(503, 'model_unavailable', 'x'))).toBe(
      'مدل زبانی در دسترس نیست',
    )
    expect(errorMessage(new ApiError(502, 'model_error', 'x'))).toBe(
      'مدل زبانی پاسخ معتبری نداد',
    )
    expect(errorMessage(new ApiError(404, 'unknown_node', 'x'))).toBe(
      'واحد انتخاب‌شده معتبر نیست',
    )
    expect(errorMessage(new ApiError(422, 'validation_error', 'x'))).toBe(
      'پرسش نامعتبر است',
    )
    expect(errorMessage(new ApiError(0, 'network_error', 'x'))).toBe(
      'ارتباط با سرور برقرار نشد',
    )
  })

  it('falls back for unknown codes', () => {
    expect(errorMessage(new ApiError(500, 'http_error', 'x'))).toBe(
      'خطای غیرمنتظره',
    )
  })
})
