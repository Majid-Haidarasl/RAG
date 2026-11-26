import { useMemo, useState } from 'react'
import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import CheckIcon from '@mui/icons-material/Check'
import CloseIcon from '@mui/icons-material/Close'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import SearchIcon from '@mui/icons-material/Search'
import Box from '@mui/material/Box'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Stack from '@mui/material/Stack'
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

type Category = {
  id: string
  title: string
  nodes: NodeOut[]
}

/** Digikala-style: left = parents that have children; right = parent + children. */
function buildCategories(nodes: NodeOut[]): Category[] {
  const parents = nodes
    .filter((n) => nodes.some((c) => c.parent_id === n.id))
    .sort(
      (a, b) => a.layer - b.layer || a.name_fa.localeCompare(b.name_fa, 'fa'),
    )

  if (parents.length === 0) {
    return [
      {
        id: 'all',
        title: 'همهٔ واحدها',
        nodes: [...nodes].sort((a, b) =>
          a.name_fa.localeCompare(b.name_fa, 'fa'),
        ),
      },
    ]
  }

  return parents.map((parent) => {
    const children = nodes
      .filter((n) => n.parent_id === parent.id)
      .sort((a, b) => a.name_fa.localeCompare(b.name_fa, 'fa'))
    return {
      id: parent.id,
      title: parent.name_fa,
      nodes: [parent, ...children],
    }
  })
}

function filterNodes(nodes: NodeOut[], q: string): NodeOut[] {
  const t = q.trim().toLowerCase()
  if (!t) return nodes
  return nodes.filter(
    (node) =>
      node.name_fa.includes(q.trim()) ||
      node.name_en.toLowerCase().includes(t) ||
      node.id.toLowerCase().includes(t),
  )
}

export function NodeSelect({
  nodes,
  value,
  onChange,
  disabled = false,
}: NodeSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeCat, setActiveCat] = useState<string | null>(null)

  const categories = useMemo(() => buildCategories(nodes), [nodes])
  const selected = nodes.find((n) => n.id === value) ?? null

  const preferredCat =
    categories.find((c) => c.nodes.some((n) => n.id === value))?.id ??
    categories[0]?.id ??
    null
  const currentCatId = activeCat ?? preferredCat
  const currentCat =
    categories.find((c) => c.id === currentCatId) ?? categories[0]

  const visibleNodes = useMemo(() => {
    if (query.trim()) {
      return filterNodes(nodes, query).sort(
        (a, b) => a.layer - b.layer || a.name_fa.localeCompare(b.name_fa, 'fa'),
      )
    }
    return currentCat?.nodes ?? []
  }, [query, nodes, currentCat])

  const selectNode = (id: string) => {
    onChange(id)
    setOpen(false)
    setQuery('')
  }

  return (
    <Box>
      <Typography
        variant="subtitle2"
        color="text.secondary"
        sx={{ mb: 1 }}
        id="node-select-label"
      >
        واحد سازمانی
      </Typography>
      <Box
        component="button"
        type="button"
        disabled={disabled}
        aria-labelledby="node-select-label"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          if (!disabled) {
            setActiveCat(preferredCat)
            setOpen(true)
          }
        }}
        sx={{
          width: '100%',
          minHeight: 52,
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          px: 1.5,
          py: 1,
          borderRadius: 1,
          border: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          cursor: disabled ? 'not-allowed' : 'pointer',
          textAlign: 'start',
          font: 'inherit',
          color: 'text.primary',
          opacity: disabled ? 0.6 : 1,
          transition: (theme) =>
            theme.transitions.create(['border-color', 'box-shadow'], {
              duration: theme.transitions.duration.shorter,
            }),
          '&:hover': disabled ? undefined : { borderColor: 'primary.main' },
          '&:focus-visible': {
            outline: '2px solid',
            outlineColor: 'primary.main',
            outlineOffset: 2,
          },
        }}
      >
        <ApartmentOutlinedIcon color="primary" aria-hidden />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body1" noWrap sx={{ fontWeight: 600 }}>
            {selected ? selected.name_fa : 'انتخاب واحد سازمانی'}
          </Typography>
          {selected ? (
            <Typography variant="caption" color="text.secondary" component="div">
              <LtrText>{selected.id}</LtrText>
              {' · '}
              لایهٔ {toPersianDigits(String(selected.layer))}
            </Typography>
          ) : (
            <Typography variant="caption" color="text.secondary">
              برای محدود کردن دامنهٔ پاسخ، واحد را انتخاب کنید
            </Typography>
          )}
        </Box>
        <KeyboardArrowDownIcon color="action" aria-hidden />
      </Box>

      <Drawer
        anchor="bottom"
        open={open}
        onClose={() => setOpen(false)}
        slotProps={{
          paper: {
            sx: {
              height: { xs: '88vh', sm: '72vh' },
              maxHeight: 640,
              borderTopLeftRadius: 16,
              borderTopRightRadius: 16,
              maxWidth: 720,
              mx: 'auto',
              width: '100%',
            },
          },
        }}
      >
        <Stack spacing={0} sx={{ height: '100%' }}>
          <Stack
            direction="row"
            sx={{
              px: 2,
              pt: 2,
              pb: 1,
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Typography variant="h6" component="h2">
              انتخاب واحد سازمانی
            </Typography>
            <IconButton
              aria-label="بستن"
              onClick={() => setOpen(false)}
              sx={{ minWidth: 44, minHeight: 44 }}
            >
              <CloseIcon />
            </IconButton>
          </Stack>

          <Box sx={{ px: 2, pb: 1.5 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="جست‌وجوی نام یا شناسه…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" aria-hidden />
                    </InputAdornment>
                  ),
                },
              }}
            />
          </Box>

          <Divider />

          <Box
            sx={{
              flex: 1,
              display: 'flex',
              minHeight: 0,
              flexDirection: { xs: 'column', sm: 'row' },
            }}
          >
            {!query.trim() && categories.length > 1 ? (
              <Box
                sx={{
                  width: { xs: '100%', sm: 200 },
                  flexShrink: 0,
                  borderInlineEnd: { sm: 1 },
                  borderBottom: { xs: 1, sm: 0 },
                  borderColor: 'divider',
                  bgcolor: 'action.hover',
                  overflow: 'auto',
                  maxHeight: { xs: 128, sm: 'none' },
                }}
              >
                <List dense disablePadding>
                  {categories.map((cat) => {
                    const active = cat.id === currentCatId
                    return (
                      <ListItemButton
                        key={cat.id}
                        selected={active}
                        onClick={() => setActiveCat(cat.id)}
                        sx={{
                          minHeight: 44,
                          borderInlineStart: 3,
                          borderColor: active ? 'primary.main' : 'transparent',
                        }}
                      >
                        <ListItemText
                          primary={cat.title}
                          slotProps={{
                            primary: {
                              variant: 'body2',
                              noWrap: true,
                              sx: { fontWeight: active ? 700 : 500 },
                            },
                          }}
                        />
                      </ListItemButton>
                    )
                  })}
                </List>
              </Box>
            ) : null}

            <Box sx={{ flex: 1, overflow: 'auto' }}>
              <List disablePadding>
                {visibleNodes.length === 0 ? (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ p: 3, textAlign: 'center' }}
                  >
                    واحدی پیدا نشد
                  </Typography>
                ) : (
                  visibleNodes.map((node) => {
                    const isSelected = node.id === value
                    const isCategoryRoot = node.id === currentCat?.id && !query.trim()
                    return (
                      <ListItemButton
                        key={node.id}
                        selected={isSelected}
                        onClick={() => selectNode(node.id)}
                        sx={{
                          minHeight: 56,
                          alignItems: 'flex-start',
                          py: 1.25,
                          ps: isCategoryRoot || query.trim() ? 1 : 3,
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 36, mt: 0.25 }}>
                          {isSelected ? (
                            <CheckIcon color="primary" fontSize="small" />
                          ) : (
                            <Box sx={{ width: 20 }} />
                          )}
                        </ListItemIcon>
                        <ListItemText
                          primary={node.name_fa}
                          secondary={
                            <Typography
                              component="span"
                              variant="caption"
                              color="text.secondary"
                            >
                              <LtrText>{node.id}</LtrText>
                              {' · '}
                              لایهٔ {toPersianDigits(String(node.layer))}
                            </Typography>
                          }
                          slotProps={{
                            primary: {
                              sx: {
                                fontWeight:
                                  isSelected || isCategoryRoot ? 700 : 500,
                              },
                            },
                          }}
                        />
                      </ListItemButton>
                    )
                  })
                )}
              </List>
            </Box>
          </Box>
        </Stack>
      </Drawer>
    </Box>
  )
}
