import { render, screen, within } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { describe, expect, it } from 'vitest'
import { answeredAsk } from '../test/fixtures'
import { theme } from '../theme'
import { CitationList } from './CitationList'

describe('CitationList', () => {
  it('lists cited sources before uncited ones', () => {
    render(
      <ThemeProvider theme={theme}>
        <CitationList
          sources={answeredAsk.sources}
          citations={answeredAsk.citations}
          highlighted={null}
        />
      </ThemeProvider>,
    )

    const accordions = screen.getAllByRole('button')
    const labels = accordions.map((btn) => {
      const text = within(btn).queryByText(/AR-HR-005/)
      return text?.textContent ?? ''
    }).filter(Boolean)

    expect(labels[0]).toContain('AR-HR-005 · بند ۱۲')
    expect(labels[1]).toContain('AR-HR-005 · بند ۱۳')
    expect(labels[2]).toContain('AR-HR-005 · بند ۱')

    expect(screen.getAllByText('استناد شده')).toHaveLength(2)
  })
})
