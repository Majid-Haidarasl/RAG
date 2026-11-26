import { useMutation, useQuery } from '@tanstack/react-query'
import { apiGet, apiPost } from './client'
import type { AskRequest, AskResponse, HealthResponse, NodesResponse } from './types'

export const queryKeys = {
  health: ['health'] as const,
  nodes: ['nodes'] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => apiGet<HealthResponse>('/api/health', signal),
    refetchInterval: (query) =>
      query.state.data?.status === 'ready' ? 60_000 : 5_000,
  })
}

export function useNodes(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.nodes,
    queryFn: ({ signal }) => apiGet<NodesResponse>('/api/nodes', signal),
    enabled,
  })
}

export function useAsk() {
  return useMutation({
    mutationFn: (body: AskRequest) => apiPost<AskResponse>('/api/ask', body),
  })
}
