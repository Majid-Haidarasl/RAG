import CheckCircleOutlinedIcon from '@mui/icons-material/CheckCircleOutlined'
import ErrorOutlinedIcon from '@mui/icons-material/ErrorOutlined'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Tooltip from '@mui/material/Tooltip'
import type { HealthResponse } from '../api/types'

export type HealthChipProps = {
  health: HealthResponse | undefined
  isError: boolean
}

function modeLabel(mode: HealthResponse['mode']): string | null {
  if (mode === 'hybrid') return 'ترکیبی'
  if (mode === 'lexical') return 'واژگانی'
  return null
}

function degradationReason(health: HealthResponse): string {
  return health.error ?? health.ollama?.reason ?? ''
}

export function HealthChip({ health, isError }: HealthChipProps) {
  if (isError || health?.status === 'error') {
    return (
      <Chip
        aria-live="polite"
        color="error"
        variant="outlined"
        icon={<ErrorOutlinedIcon />}
        label="خطا"
        size="small"
      />
    )
  }

  if (!health || health.status === 'loading') {
    return (
      <Chip
        aria-live="polite"
        color="default"
        variant="outlined"
        icon={<CircularProgress size={14} color="inherit" />}
        label="در حال آماده‌سازی"
        size="small"
      />
    )
  }

  if (health.status === 'degraded') {
    const reason = degradationReason(health)
    const chip = (
      <Chip
        aria-live="polite"
        color="warning"
        variant="outlined"
        icon={<WarningAmberIcon />}
        label="ناقص"
        size="small"
      />
    )
    return reason ? <Tooltip title={reason}>{chip}</Tooltip> : chip
  }

  const mode = modeLabel(health.mode)
  const label = mode ? `آماده · ${mode}` : 'آماده'

  return (
    <Chip
      aria-live="polite"
      color="success"
      variant="outlined"
      icon={<CheckCircleOutlinedIcon />}
      label={label}
      size="small"
    />
  )
}
