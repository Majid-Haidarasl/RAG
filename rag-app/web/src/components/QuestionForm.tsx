import type { KeyboardEvent } from 'react'
import { useState } from 'react'
import CloseIcon from '@mui/icons-material/Close'
import ListAltOutlinedIcon from '@mui/icons-material/ListAltOutlined'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { questionsForNode } from '../data/sampleQuestions'
import { toPersianDigits } from '../lib/digits'
import { LtrText } from './LtrText'

export type QuestionFormProps = {
  onSubmit: (question: string) => void
  pending?: boolean
  disabled?: boolean
  maxChars?: number
  nodeId?: string
  nodeNameFa?: string
}

export function QuestionForm({
  onSubmit,
  pending = false,
  disabled = false,
  maxChars = 2000,
  nodeId = '',
  nodeNameFa,
}: QuestionFormProps) {
  const [text, setText] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const trimmed = text.trim()
  const canSubmit = !pending && !disabled && trimmed.length > 0
  const samples = nodeId ? questionsForNode(nodeId) : []
  const persianSamples = samples.slice(0, 5)
  const englishSamples = samples.slice(5, 10)

  const submit = () => {
    if (!canSubmit) return
    onSubmit(trimmed)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      submit()
    }
  }

  const fillQuestion = (q: string) => {
    if (disabled || pending) return
    setText(q.slice(0, maxChars))
    setDrawerOpen(false)
  }

  const counter = `${toPersianDigits(String(text.length))} / ${toPersianDigits(String(maxChars))}`

  return (
    <Stack
      spacing={1.5}
      component="form"
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <TextField
        label="سؤال شما"
        multiline
        minRows={3}
        fullWidth
        value={text}
        disabled={disabled || pending}
        onChange={(e) => {
          const next = e.target.value
          if (next.length <= maxChars) setText(next)
        }}
        onKeyDown={handleKeyDown}
        slotProps={{
          htmlInput: {
            maxLength: maxChars,
            'aria-describedby': 'question-char-count',
          },
        }}
        helperText={
          <Typography
            id="question-char-count"
            component="span"
            variant="caption"
            color="text.secondary"
          >
            {counter}
          </Typography>
        }
      />

      <Button
        type="button"
        variant="outlined"
        color="primary"
        disabled={disabled || pending || !nodeId || samples.length === 0}
        startIcon={<ListAltOutlinedIcon />}
        onClick={() => setDrawerOpen(true)}
        sx={{ alignSelf: 'stretch', justifyContent: 'flex-start' }}
      >
        نمونه‌سؤال‌های قابل پرسش
        {nodeNameFa ? ` · ${nodeNameFa}` : ''}
      </Button>

      <Button
        type="submit"
        variant="contained"
        color="primary"
        disabled={!canSubmit}
        aria-busy={pending || undefined}
        startIcon={
          pending ? <CircularProgress size={18} color="inherit" /> : undefined
        }
        sx={{ alignSelf: 'flex-start', minWidth: 120 }}
      >
        {pending ? 'در حال یافتن پاسخ…' : 'بپرس'}
      </Button>

      <Drawer
        anchor="bottom"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        slotProps={{
          paper: {
            sx: {
              height: { xs: '85vh', sm: '75vh' },
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
        <Stack sx={{ height: '100%' }}>
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
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6" component="h2" noWrap>
                نمونه‌سؤال‌ها
              </Typography>
              {nodeNameFa ? (
                <Typography variant="body2" color="text.secondary" noWrap>
                  {nodeNameFa}
                  {' · '}
                  {toPersianDigits('5')} فارسی و {toPersianDigits('5')} انگلیسی
                </Typography>
              ) : null}
            </Box>
            <IconButton
              aria-label="بستن"
              onClick={() => setDrawerOpen(false)}
              sx={{ minWidth: 44, minHeight: 44 }}
            >
              <CloseIcon />
            </IconButton>
          </Stack>
          <Divider />
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            <Typography
              variant="subtitle2"
              color="primary"
              sx={{ px: 2, pt: 2, pb: 0.5 }}
            >
              فارسی
            </Typography>
            <List disablePadding>
              {persianSamples.map((q, index) => (
                <ListItemButton
                  key={`fa-${q}`}
                  onClick={() => fillQuestion(q)}
                  sx={{ minHeight: 56, alignItems: 'flex-start', py: 1.5 }}
                >
                  <ListItemText
                    primary={`${toPersianDigits(String(index + 1))}. ${q}`}
                  />
                </ListItemButton>
              ))}
            </List>

            <Divider sx={{ my: 1 }} />

            <Typography
              variant="subtitle2"
              color="primary"
              sx={{ px: 2, pt: 1, pb: 0.5 }}
            >
              <LtrText>English</LtrText>
            </Typography>
            <List disablePadding>
              {englishSamples.map((q, index) => (
                <ListItemButton
                  key={`en-${q}`}
                  onClick={() => fillQuestion(q)}
                  sx={{ minHeight: 56, alignItems: 'flex-start', py: 1.5 }}
                >
                  <ListItemText
                    primary={
                      <Typography
                        component="span"
                        variant="body1"
                        dir="ltr"
                        sx={{ display: 'block', textAlign: 'left' }}
                      >
                        <LtrText>
                          {toPersianDigits(String(index + 6))}. {q}
                        </LtrText>
                      </Typography>
                    }
                  />
                </ListItemButton>
              ))}
            </List>
          </Box>
        </Stack>
      </Drawer>
    </Stack>
  )
}
