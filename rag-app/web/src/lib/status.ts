import { ApiError } from '../api/client'
import type { QaStatus } from '../api/types'

export type StatusColor = 'success' | 'warning' | 'default' | 'info'
export type StatusIcon = 'ok' | 'warn' | 'none' | 'route'

export type StatusView = {
  label: string
  color: StatusColor
  icon: StatusIcon
}

export function statusView(status: QaStatus, grounded: boolean): StatusView {
  switch (status) {
    case 'answered':
      return grounded
        ? { label: 'پاسخ مستند', color: 'success', icon: 'ok' }
        : { label: 'پاسخ بدون ارجاع معتبر', color: 'warning', icon: 'warn' }
    case 'insufficient_context':
      return { label: 'شواهد کافی نیست', color: 'warning', icon: 'warn' }
    case 'not_found_in_scope':
      return {
        label: 'در دامنهٔ این واحد پیدا نشد',
        color: 'default',
        icon: 'none',
      }
    case 'out_of_scope':
      return {
        label: 'خارج از دامنه، ارجاع به واحد دیگر',
        color: 'info',
        icon: 'route',
      }
  }
}

const ERROR_MESSAGES: Record<string, string> = {
  warming_up: 'سیستم در حال آماده‌سازی است؛ چند لحظه بعد دوباره بپرسید',
  startup_failed: 'راه‌اندازی سرور ناموفق بود',
  model_unavailable: 'مدل زبانی در دسترس نیست',
  model_error: 'مدل زبانی پاسخ معتبری نداد',
  unknown_node: 'واحد انتخاب‌شده معتبر نیست',
  validation_error: 'پرسش نامعتبر است',
  network_error: 'ارتباط با سرور برقرار نشد',
}

export function errorMessage(err: ApiError): string {
  return ERROR_MESSAGES[err.code] ?? 'خطای غیرمنتظره'
}
