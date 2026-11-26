import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, expect, it, vi } from 'vitest'
import { answeredAsk, outOfScopeAsk } from '../test/fixtures'
import { theme } from '../theme'
import { AnswerCard } from './AnswerCard'

describe('AnswerCard', () => {
  it('renders a citation chip per cite segment', () => {
    render(
      <ThemeProvider theme={theme}>
        <AnswerCard
          answer={answeredAsk}
          question="سقف مرخصی؟"
          onCiteClick={vi.fn()}
        />
      </ThemeProvider>,
    )

    expect(screen.getByText('AR-HR-005 · بند ۱۲')).toBeInTheDocument()
    expect(screen.getByText('AR-HR-005 · بند ۱۳')).toBeInTheDocument()
    expect(screen.getAllByRole('button').filter((el) =>
      /AR-HR-005/.test(el.textContent ?? ''),
    )).toHaveLength(2)
  })

  it('calls onCiteClick with the citation label', async () => {
    const user = userEvent.setup()
    const onCiteClick = vi.fn()
    render(
      <ThemeProvider theme={theme}>
        <AnswerCard
          answer={answeredAsk}
          question="سقف مرخصی؟"
          onCiteClick={onCiteClick}
        />
      </ThemeProvider>,
    )

    await user.click(screen.getByText('AR-HR-005 · بند ۱۲'))
    expect(onCiteClick).toHaveBeenCalledWith('AR-HR-005 §12')
  })

  it('shows escalation target name for out_of_scope', () => {
    render(
      <ThemeProvider theme={theme}>
        <AnswerCard
          answer={outOfScopeAsk}
          question="سقف مرخصی بدون حقوق؟"
          onCiteClick={vi.fn()}
        />
      </ThemeProvider>,
    )

    expect(screen.getByText(/پیشنهاد ارجاع به:/)).toBeInTheDocument()
    expect(screen.getByText(/مدیرعامل/)).toBeInTheDocument()
  })
})
