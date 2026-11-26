import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import type { NodeOut } from '../api/types'
import { toPersianDigits } from '../lib/digits'
import { LtrText } from './LtrText'

export type NodeSelectProps = {
  nodes: NodeOut[]
  value: string
  onChange: (nodeId: string) => void
  disabled?: boolean
}

function layerGroupTitle(layer: number): string {
  return `لایهٔ ${toPersianDigits(String(layer))}`
}

function filterNodes(options: NodeOut[], inputValue: string): NodeOut[] {
  const q = inputValue.trim().toLowerCase()
  if (!q) return options
  return options.filter(
    (node) =>
      node.name_fa.includes(inputValue.trim()) ||
      node.name_en.toLowerCase().includes(q) ||
      node.id.toLowerCase().includes(q),
  )
}

export function NodeSelect({
  nodes,
  value,
  onChange,
  disabled = false,
}: NodeSelectProps) {
  const options = [...nodes].sort(
    (a, b) => a.layer - b.layer || a.name_fa.localeCompare(b.name_fa, 'fa'),
  )
  const selected = options.find((node) => node.id === value) ?? null

  return (
    <Autocomplete
      options={options}
      value={selected}
      disabled={disabled}
      fullWidth
      groupBy={(option) => layerGroupTitle(option.layer)}
      getOptionLabel={(option) => option.name_fa}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      noOptionsText="واحدی پیدا نشد"
      filterOptions={(opts, state) => filterNodes(opts, state.inputValue)}
      onChange={(_, node) => {
        if (node) onChange(node.id)
      }}
      renderOption={(props, option) => {
        const { key, ...rest } = props
        return (
          <Box
            component="li"
            key={key}
            {...rest}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              gap: 0.25,
            }}
          >
            <Typography component="span" variant="body1">
              {option.name_fa}
            </Typography>
            <Typography
              component="span"
              variant="body2"
              color="text.secondary"
            >
              <LtrText>{option.id}</LtrText>
            </Typography>
          </Box>
        )
      }}
      renderInput={(params) => (
        <TextField {...params} label="واحد سازمانی" />
      )}
    />
  )
}
