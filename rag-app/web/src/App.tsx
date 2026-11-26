import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Container from '@mui/material/Container'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import { useHealth, useNodes } from './api/hooks'
import { HealthChip } from './components/HealthChip'
import { NodeSelect } from './components/NodeSelect'

const NODE_STORAGE_KEY = 'rag.node'

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

function App() {
  const healthQuery = useHealth()
  const health = healthQuery.data
  const nodesEnabled =
    health?.status === 'ready' || health?.status === 'degraded'
  const nodesQuery = useNodes(Boolean(nodesEnabled))
  const [nodeId, setNodeId] = useState(readStoredNodeId)

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

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack spacing={3} sx={{ alignItems: 'stretch' }}>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1.5,
          }}
        >
          <Typography variant="h4" component="h1" color="primary">
            دستیار دانش آرمان‌رایان
          </Typography>
          <HealthChip health={health} isError={healthQuery.isError} />
        </Box>
        <NodeSelect
          nodes={nodesQuery.data?.nodes ?? []}
          value={nodeId}
          onChange={handleNodeChange}
          disabled={!nodesQuery.data}
        />
      </Stack>
    </Container>
  )
}

export default App
