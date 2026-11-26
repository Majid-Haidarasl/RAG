import type { ComponentProps } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, expect, it, vi } from 'vitest'
import { theme } from '../theme'
import { QuestionForm } from './QuestionForm'

function renderForm(
  props: Partial<ComponentProps<typeof QuestionForm>> = {},
) {
  const onSubmit = props.onSubmit ?? vi.fn()
  render(
    <ThemeProvider theme={theme}>
      <QuestionForm
        onSubmit={onSubmit}
        pending={props.pending}
        disabled={props.disabled}
        maxChars={props.maxChars}
      />
    </ThemeProvider>,
  )
  return { onSubmit }
}

describe('QuestionForm', () => {
  it('does not submit empty or whitespace-only text', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    expect(screen.getByRole('button', { name: 'بپرس' })).toBeDisabled()

    await user.type(screen.getByLabelText('سؤال شما'), '   ')
    expect(screen.getByRole('button', { name: 'بپرس' })).toBeDisabled()

    await user.keyboard('{Control>}{Enter}{/Control}')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits trimmed text on Ctrl+Enter', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()
    const field = screen.getByLabelText('سؤال شما')

    await user.type(field, '  پرسش نمونه  ')
    await user.keyboard('{Control>}{Enter}{/Control}')

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('پرسش نمونه')
  })

  it('disables the button while pending and shows spinner label', () => {
    renderForm({ pending: true })

    const button = screen.getByRole('button', { name: /در حال یافتن پاسخ/ })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})
