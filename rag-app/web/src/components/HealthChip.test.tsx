import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, expect, it } from 'vitest'
import type { HealthResponse } from '../api/types'
import { theme } from '../theme'
import { HealthChip } from './HealthChip'

const base: Omit<HealthResponse, 'status' | 'mode' | 'can_answer' | 'error'> = {
  core_version: '0.1.0',
  api_version: '0.1.0',
  ollama: null,
  index: null,
}

function renderChip(
  health: HealthResponse | undefined,
  isError = false,
) {
  return render(
    <ThemeProvider theme={theme}>
      <HealthChip health={health} isError={isError} />
    </ThemeProvider>,
  )
}

describe('HealthChip', () => {
  it('shows loading state with spinner text', () => {
    renderChip({
      ...base,
      status: 'loading',
      mode: null,
      can_answer: false,
      error: null,
    })
    expect(screen.getByText('در حال آماده‌سازی')).toBeInTheDocument()
  })

  it('shows ready state without mode suffix', () => {
    renderChip({
      ...base,
      status: 'ready',
      mode: 'hybrid',
      can_answer: true,
      error: null,
    })
    expect(screen.getByText('آماده')).toBeInTheDocument()
    expect(screen.queryByText(/ترکیبی/)).not.toBeInTheDocument()
  })

  it('shows fake mode as experimental', () => {
    renderChip({
      ...base,
      status: 'ready',
      mode: 'fake',
      can_answer: true,
      error: null,
    })
    expect(screen.getByText('آزمایشی')).toBeInTheDocument()
  })

  it('shows degraded state and tooltip reason from ollama.reason', async () => {
    const user = userEvent.setup()
    renderChip({
      ...base,
      status: 'degraded',
      mode: 'lexical',
      can_answer: false,
      error: null,
      ollama: {
        reachable: false,
        version: null,
        base_url: 'http://127.0.0.1:11434',
        reason: 'Ollama not reachable',
        models: [],
      },
    })

    const chip = screen.getByText('ناقص')
    expect(chip).toBeInTheDocument()
    await user.hover(chip)
    expect(await screen.findByText('Ollama not reachable')).toBeInTheDocument()
  })

  it('shows error state when isError or status is error', () => {
    const { rerender } = renderChip(undefined, true)
    expect(screen.getByText('خطا')).toBeInTheDocument()

    rerender(
      <ThemeProvider theme={theme}>
        <HealthChip
          health={{
            ...base,
            status: 'error',
            mode: null,
            can_answer: false,
            error: 'startup failed',
          }}
          isError={false}
        />
      </ThemeProvider>,
    )
    expect(screen.getByText('خطا')).toBeInTheDocument()
  })
})
