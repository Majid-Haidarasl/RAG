import { useEffect, useRef, useState } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import type { CitationOut, SourceOut } from '../api/types'
import { formatCitationLabel } from '../lib/citations'
import { toPersianDigits } from '../lib/digits'
import { LtrText } from './LtrText'

export type CitationListProps = {
  sources: SourceOut[]
  citations: CitationOut[]
  highlighted: string | null
}

function sourceMeta(source: SourceOut): string {
  const parts: string[] = [
    source.version,
    source.language,
  ]
  if (source.page != null) {
    parts.push(`صفحه ${toPersianDigits(String(source.page))}`)
  } else if (source.paragraph != null) {
    parts.push(`بند ${toPersianDigits(String(source.paragraph))}`)
  }
  return parts.filter(Boolean).join(' · ')
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function CitationList({
  sources,
  citations,
  highlighted,
}: CitationListProps) {
  const ordered = [
    ...sources.filter((s) => s.cited),
    ...sources.filter((s) => !s.cited),
  ]
  // citations kept for API parity with AnswerCard consumers
  void citations
  const [expanded, setExpanded] = useState<string | false>(false)
  const [flashKey, setFlashKey] = useState<string | null>(null)
  const refs = useRef<Map<string, HTMLDivElement | null>>(new Map())

  useEffect(() => {
    if (!highlighted) return
    const match =
      sources.find((s) => s.label === highlighted) ??
      sources.find((s) => s.document_id === highlighted.split(' ')[0])
    if (!match) return
    setExpanded(match.key)
    setFlashKey(match.key)
    const el = refs.current.get(match.key)
    if (el) {
      const behavior: ScrollBehavior = prefersReducedMotion()
        ? 'instant'
        : 'smooth'
      el.scrollIntoView({ behavior, block: 'nearest' })
    }
    const t = window.setTimeout(() => setFlashKey(null), 1200)
    return () => window.clearTimeout(t)
  }, [highlighted, sources])

  if (ordered.length === 0) return null

  return (
    <Stack spacing={1}>
      {ordered.map((source) => (
        <Accordion
          key={source.key}
          expanded={expanded === source.key}
          onChange={(_, isExpanded) =>
            setExpanded(isExpanded ? source.key : false)
          }
          disableGutters
          ref={(node: HTMLDivElement | null) => {
            refs.current.set(source.key, node)
          }}
          sx={{
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            backgroundColor:
              flashKey === source.key ? 'action.selected' : 'background.paper',
            transition: (theme) =>
              theme.transitions.create('background-color', {
                duration: theme.transitions.duration.short,
              }),
            '&:before': { display: 'none' },
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            sx={{ minHeight: 44, '& .MuiAccordionSummary-content': { my: 1 } }}
          >
            <Stack spacing={0.5} sx={{ width: '100%', pr: 1 }}>
              <Stack
                direction="row"
                spacing={1}
                useFlexGap
                sx={{ flexWrap: 'wrap', alignItems: 'center' }}
              >
                <Typography variant="body2" component="span">
                  <LtrText>{formatCitationLabel(source.label)}</LtrText>
                </Typography>
                {source.cited ? (
                  <Chip size="small" color="primary" label="استناد شده" />
                ) : null}
              </Stack>
              <Typography variant="body2">{source.title_fa}</Typography>
              <Typography variant="caption" color="text.secondary">
                {sourceMeta(source)}
              </Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            {source.heading_path.length > 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {source.heading_path.join(' › ')}
              </Typography>
            ) : null}
            <Box dir="auto" sx={{ whiteSpace: 'pre-wrap' }}>
              {source.excerpt}
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}
    </Stack>
  )
}
