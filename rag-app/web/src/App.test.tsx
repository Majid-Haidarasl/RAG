import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CacheProvider } from '@emotion/react'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { answeredAsk } from './test/fixtures'
import { rtlCache } from './rtlCache'
import { theme } from './theme'

const healthReady = {
  status: 'ready',
  mode: 'hybrid',
  can_answer: true,
  core_version: '1.0.0',
  api_version: '0.1.0',
  error: null,
  ollama: null,
  index: null,
}

const nodesBody = {
  default_node_id: 'N-ADM-HR',
  nodes: [
    {
      id: 'N-ADM-HR',
      name_fa: 'منابع انسانی',
      name_en: 'Human Resources',
      node_type: 'unit',
      layer: 1,
      parent_id: 'N-CEO',
    },
    {
      id: 'N-CEO',
      name_fa: 'مدیرعامل',
      name_en: 'CEO',
      node_type: 'unit',
      layer: 0,
      parent_id: null,
    },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
  return render(
    <CacheProvider value={rtlCache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <QueryClientProvider client={client}>
          <App />
        </QueryClientProvider>
      </ThemeProvider>
    </CacheProvider>,
  )
}

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('full flow: pick node, ask, see answer text and a citation chip', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/api/health')) return jsonResponse(healthReady)
      if (url.includes('/api/nodes')) return jsonResponse(nodesBody)
      if (url.includes('/api/ask') && init?.method === 'POST') {
        return jsonResponse(answeredAsk)
      }
      return jsonResponse({ error: { code: 'http_error', message: 'miss' } }, 404)
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'واحد سازمانی' })).toHaveTextContent(
        'منابع انسانی',
      )
    })

    await user.click(screen.getByRole('button', { name: 'واحد سازمانی' }))
    await user.type(
      await screen.findByPlaceholderText(/جست/),
      'مدیرعامل',
    )
    await user.click(await screen.findByRole('button', { name: /مدیرعامل/ }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'واحد سازمانی' })).toHaveTextContent(
        'مدیرعامل',
      )
    })

    await user.click(screen.getByRole('button', { name: 'واحد سازمانی' }))
    await user.type(
      await screen.findByPlaceholderText(/جست/),
      'منابع انسانی',
    )
    await user.click(await screen.findByRole('button', { name: /منابع انسانی/ }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'واحد سازمانی' })).toHaveTextContent(
        'منابع انسانی',
      )
    })

    const question =
      'سقف مرخصی ساعتی در روز و در ماه چقدر است؟'
    await user.type(screen.getByLabelText('سؤال شما'), question)
    await user.click(screen.getByRole('button', { name: 'بپرس' }))

    await waitFor(() => {
      expect(
        screen.getByText(/سقف مرخصی ساعتی در روز ۴ ساعت است/),
      ).toBeInTheDocument()
    })
    expect(
      screen.getAllByText('AR-HR-005 · بند ۱۲').length,
    ).toBeGreaterThanOrEqual(1)

    const askCalls = fetchMock.mock.calls.filter(([u]) =>
      String(u).includes('/api/ask'),
    )
    expect(askCalls).toHaveLength(1)
    const body = JSON.parse(String(askCalls[0][1]?.body))
    expect(body.node_id).toBe('N-ADM-HR')
    expect(body.question).toBe(question)
  })

  it('shows persistent fake-mode warning', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/api/health')) {
        return jsonResponse({ ...healthReady, mode: 'fake' })
      }
      if (url.includes('/api/nodes')) return jsonResponse(nodesBody)
      return jsonResponse({ error: { code: 'http_error', message: 'miss' } }, 404)
    })

    renderApp()

    expect(
      await screen.findByText('حالت آزمایشی — پاسخ‌ها واقعی نیستند'),
    ).toBeInTheDocument()
    expect(screen.getByText('آزمایشی')).toBeInTheDocument()
  })

  it('shows Persian warming_up message on 503', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/api/health')) return jsonResponse(healthReady)
      if (url.includes('/api/nodes')) return jsonResponse(nodesBody)
      if (url.includes('/api/ask') && init?.method === 'POST') {
        return jsonResponse(
          {
            error: {
              code: 'warming_up',
              message: 'warming up',
            },
          },
          503,
        )
      }
      return jsonResponse({ error: { code: 'http_error', message: 'miss' } }, 404)
    })

    renderApp()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'واحد سازمانی' })).toHaveTextContent(
        'منابع انسانی',
      )
    })

    await user.type(screen.getByLabelText('سؤال شما'), 'پرسش آزمایشی')
    await user.click(screen.getByRole('button', { name: 'بپرس' }))

    expect(
      await screen.findByText(
        'سیستم در حال آماده‌سازی است؛ چند لحظه بعد دوباره بپرسید',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'تلاش دوباره' }),
    ).toBeInTheDocument()
  })
})
