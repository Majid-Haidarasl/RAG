import AltRouteIcon from '@mui/icons-material/AltRoute'
import CheckCircleOutlinedIcon from '@mui/icons-material/CheckCircleOutlined'
import HelpOutlinedIcon from '@mui/icons-material/HelpOutlined'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CardHeader from '@mui/material/CardHeader'
import Chip from '@mui/material/Chip'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import type { AskResponse } from '../api/types'
import { formatCitationLabel, splitCitations } from '../lib/citations'
import { toPersianDigits } from '../lib/digits'
import { statusView, type StatusIcon } from '../lib/status'
import { LtrText } from './LtrText'

export type AnswerCardProps = {
  answer: AskResponse
  question: string
  onCiteClick: (label: string) => void
}

function StatusIconEl({ icon }: { icon: StatusIcon }) {
  switch (icon) {
    case 'ok':
      return <CheckCircleOutlinedIcon fontSize="small" />
    case 'warn':
      return <WarningAmberIcon fontSize="small" />
    case 'route':
      return <AltRouteIcon fontSize="small" />
    case 'none':
      return <HelpOutlinedIcon fontSize="small" />
  }
}

export function AnswerCard({ answer, question, onCiteClick }: AnswerCardProps) {
  const view = statusView(answer.status, answer.grounded)
  const invalidLabels = new Set(
    answer.citations.filter((c) => !c.valid).map((c) => c.label),
  )
  const segments = splitCitations(answer.text)
  const total = answer.timings_s.total
  const totalFa =
    total != null ? toPersianDigits(String(total)) : null

  return (
    <Card variant="outlined">
      <CardHeader
        title={
          <Typography variant="subtitle1" component="h2">
            {question}
          </Typography>
        }
        subheader={
          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            sx={{ flexWrap: 'wrap', alignItems: 'center', mt: 1 }}
          >
            <Chip
              size="small"
              color={view.color}
              variant="outlined"
              icon={<StatusIconEl icon={view.icon} />}
              label={view.label}
            />
            {answer.node_name_fa ? (
              <Typography variant="body2" color="text.secondary">
                {answer.node_name_fa}
              </Typography>
            ) : null}
          </Stack>
        }
      />
      <CardContent>
        <Box
          component="div"
          sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, mb: 2 }}
        >
          {segments.map((seg, i) => {
            if (seg.kind === 'text') {
              return <span key={`t-${i}`}>{seg.text}</span>
            }
            const invalid = invalidLabels.has(seg.label)
            const chip = (
              <Chip
                size="small"
                color={invalid ? 'error' : 'primary'}
                variant="outlined"
                label={<LtrText>{formatCitationLabel(seg.label)}</LtrText>}
                onClick={() => onCiteClick(seg.label)}
                sx={{
                  mx: 0.25,
                  my: 0.25,
                  verticalAlign: 'middle',
                  maxWidth: '100%',
                  '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' },
                }}
              />
            )
            if (invalid) {
              return (
                <Tooltip
                  key={`c-${i}-${seg.label}`}
                  title="این ارجاع در منابع بازیابی‌شده نیست"
                >
                  <span>{chip}</span>
                </Tooltip>
              )
            }
            return <span key={`c-${i}-${seg.label}`}>{chip}</span>
          })}
        </Box>

        {answer.status === 'out_of_scope' && answer.escalation ? (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              پیشنهاد ارجاع به:{' '}
              {answer.escalation.target_name_fa ?? answer.escalation.target}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {answer.escalation.reason}
            </Typography>
          </Alert>
        ) : null}

        {answer.fact_flags.length > 0 ? (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              برخی اعداد یا شناسه‌ها در منابع تأیید نشدند
            </Typography>
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', mt: 1 }}>
              {answer.fact_flags.map((flag) => (
                <Chip
                  key={flag}
                  size="small"
                  variant="outlined"
                  label={<LtrText>{flag}</LtrText>}
                />
              ))}
            </Stack>
          </Alert>
        ) : null}

        <Typography variant="caption" color="text.secondary" component="p">
          {answer.model ? (
            <>
              <LtrText>{answer.model}</LtrText>
              {totalFa != null ? ' · ' : null}
            </>
          ) : null}
          {totalFa != null ? `${totalFa} ثانیه` : null}
        </Typography>
      </CardContent>
    </Card>
  )
}
