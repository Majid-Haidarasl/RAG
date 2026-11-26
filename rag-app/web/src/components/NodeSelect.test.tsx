import type { ComponentProps } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, expect, it, vi } from 'vitest'
import type { NodeOut } from '../api/types'
import { theme } from '../theme'
import { NodeSelect } from './NodeSelect'

const nodes: NodeOut[] = [
  {
    id: 'N-CEO',
    name_fa: 'مدیرعامل',
    name_en: 'CEO',
    node_type: 'unit',
    layer: 0,
    parent_id: null,
  },
  {
    id: 'N-ADM-HR',
    name_fa: 'منابع انسانی',
    name_en: 'Human Resources',
    node_type: 'unit',
    layer: 1,
    parent_id: 'N-CEO',
  },
  {
    id: 'N-FIN',
    name_fa: 'مالی',
    name_en: 'Finance',
    node_type: 'unit',
    layer: 1,
    parent_id: 'N-CEO',
  },
]

function renderSelect(
  props: Partial<ComponentProps<typeof NodeSelect>> = {},
) {
  const onChange = props.onChange ?? vi.fn()
  render(
    <ThemeProvider theme={theme}>
      <NodeSelect
        nodes={nodes}
        value={props.value ?? ''}
        onChange={onChange}
        disabled={props.disabled}
      />
    </ThemeProvider>,
  )
  return { onChange }
}

describe('NodeSelect', () => {
  it('filters by Persian name and shows the node id', async () => {
    const user = userEvent.setup()
    renderSelect()

    await user.click(screen.getByRole('button', { name: 'واحد سازمانی' }))
    await user.type(await screen.findByPlaceholderText(/جست/), 'منابع انسانی')

    expect(await screen.findByText('N-ADM-HR')).toBeInTheDocument()
    expect(screen.queryByText('N-FIN')).not.toBeInTheDocument()
  })

  it('calls onChange with the selected node id', async () => {
    const user = userEvent.setup()
    const { onChange } = renderSelect()

    await user.click(screen.getByRole('button', { name: 'واحد سازمانی' }))
    await user.type(await screen.findByPlaceholderText(/جست/), 'منابع انسانی')
    await user.click(await screen.findByRole('button', { name: /منابع انسانی/ }))

    expect(onChange).toHaveBeenCalledWith('N-ADM-HR')
  })
})
