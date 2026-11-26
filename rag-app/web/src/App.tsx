import { useEffect, useId, useState } from 'react'
import Alert from '@mui/material/Alert'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Container from '@mui/material/Container'
import Skeleton from '@mui/material/Skeleton'
import Stack from '@mui/material/Stack'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import { ApiError } from './api/client'
import { useAsk, useHealth, useNodes } from './api/hooks'
import type { AskResponse } from './api/types'
import { AnswerCard } from './components/AnswerCard'
import { CitationList } from './components/CitationList'
import { NodeSelect } from './components/NodeSelect'
import { QuestionForm } from './components/QuestionForm'
import { errorMessage } from './lib/status'

const NODE_STORAGE_KEY = 'rag.node'

type SessionItem = {
  id: string
  question: string
  node_id: string
  answer?: AskResponse
  error?: ApiError
}

function readStoredNodeId(): string {
  try {
    return localStorage.getItem(NODE_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function writeStoredNodeId(nodeId: string): void {
  try {
    localStorage.setItem(NODE_STORAGE_KEY, nodeId)
  } catch {
    // ignore quota / private-mode failures
  }
}

function AnswerSkeleton() {
  return (
    <Card variant="outlined" aria-busy="true" aria-label="در حال یافتن پاسخ">
      <CardContent>
        <Skeleton variant="text" width="60%" height={28} />
        <Skeleton variant="rounded" height={20} width={120} sx={{ mt: 1, mb: 2 }} />
        <Skeleton variant="rectangular" height={96} sx={{ borderRadius: 1 }} />
        <Skeleton variant="text" width="40%" sx={{ mt: 2 }} />
      </CardContent>
    </Card>
  )
}

function App() {
  const healthQuery = useHealth()
  const health = healthQuery.data
  const nodesEnabled =
    health?.status === 'ready' || health?.status === 'degraded'
  const nodesQuery = useNodes(Boolean(nodesEnabled))
  const ask = useAsk()
  const [nodeId, setNodeId] = useState(readStoredNodeId)
  const [current, setCurrent] = useState<SessionItem | null>(null)
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const idPrefix = useId()
  const [seq, setSeq] = useState(0)

  useEffect(() => {
    const data = nodesQuery.data
    if (!data) return
    const known = new Set(data.nodes.map((node) => node.id))
    if (nodeId && known.has(nodeId)) return
    setNodeId(data.default_node_id)
    writeStoredNodeId(data.default_node_id)
  }, [nodesQuery.data, nodeId])

  const handleNodeChange = (next: string) => {
    setNodeId(next)
    writeStoredNodeId(next)
  }

  const healthLoading = !health || health.status === 'loading'
  const healthDegraded = health?.status === 'degraded'
  const cannotAnswer =
    healthLoading ||
    health?.status === 'error' ||
    healthQuery.isError ||
    (health != null && !health.can_answer)
  const formDisabled = cannotAnswer || !nodeId || ask.isPending

  const degradationReason =
    health?.error ?? health?.ollama?.reason ?? 'وضعیت ناقص'

  const submitQuestion = (question: string, targetNodeId = nodeId) => {
    if (!targetNodeId || cannotAnswer) return
    const id = `${idPrefix}-${seq}`
    setSeq((n) => n + 1)
    setHighlighted(null)
    ask.mutate(
      { question, node_id: targetNodeId },
      {
        onSuccess: (answer) => {
          setCurrent({ id, question, node_id: targetNodeId, answer })
        },
        onError: (err) => {
          const error =
            err instanceof ApiError
              ? err
              : new ApiError(0, 'network_error', 'Network error')
          setCurrent({ id, question, node_id: targetNodeId, error })
        },
      },
    )
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        overflowX: 'hidden',
      }}
    >
      <AppBar
        position="sticky"
        elevation={0}
        color="primary"
        sx={{ borderBottom: 1, borderColor: 'primary.dark' }}
      >
        <Toolbar
          sx={{
            gap: 1.5,
            flexWrap: 'wrap',
            minHeight: { xs: 56, sm: 64 },
            py: 1,
          }}
        >
          <Typography
            variant="h6"
            component="h1"
            sx={{ flexGrow: 1, minWidth: 0, lineHeight: 1.4, color: 'primary.contrastText' }}
          >
            دستیار دانش آرمان‌رایان
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: { xs: 3, sm: 4 }, px: { xs: 2, sm: 3 } }}>
        <Stack spacing={3} sx={{ alignItems: 'stretch' }}>
          {healthLoading ? (
            <Alert severity="info">سیستم در حال آماده‌سازی است…</Alert>
          ) : null}

          {healthDegraded && !healthLoading ? (
            <Alert severity="warning">{degradationReason}</Alert>
          ) : null}

          <NodeSelect
            nodes={nodesQuery.data?.nodes ?? []}
            value={nodeId}
            onChange={handleNodeChange}
            disabled={!nodesQuery.data || healthLoading}
          />

          <QuestionForm
            onSubmit={submitQuestion}
            pending={ask.isPending}
            disabled={formDisabled && !ask.isPending}
            nodeId={nodeId}
            nodeNameFa={
              nodesQuery.data?.nodes.find((n) => n.id === nodeId)?.name_fa
            }
          />

          {ask.isPending ? <AnswerSkeleton /> : null}

          {!ask.isPending && current == null ? (
            <Typography variant="body2" color="text.secondary">
              یک واحد را انتخاب کنید و سؤال خود را بپرسید تا پاسخ مستند با منابع
              نمایش داده شود.
            </Typography>
          ) : null}

          {current && !ask.isPending ? (
            <Stack spacing={2}>
              {current.error ? (
                <Alert
                  severity="error"
                  action={
                    <Button
                      color="inherit"
                      size="small"
                      onClick={() =>
                        submitQuestion(current.question, current.node_id)
                      }
                      sx={{ minHeight: 44 }}
                    >
                      تلاش دوباره
                    </Button>
                  }
                >
                  {errorMessage(current.error)}
                </Alert>
              ) : current.answer ? (
                <>
                  <AnswerCard
                    answer={current.answer}
                    question={current.question}
                    onCiteClick={setHighlighted}
                  />
                  <CitationList
                    sources={current.answer.sources}
                    citations={current.answer.citations}
                    highlighted={highlighted}
                  />
                </>
              ) : null}
            </Stack>
          ) : null}
        </Stack>
      </Container>
    </Box>
  )
}

export default App
