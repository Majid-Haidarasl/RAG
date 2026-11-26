import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  direction: 'rtl',
  palette: {
    primary: {
      main: '#7C3AED',
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: '#0891B2',
    },
    error: {
      main: '#DC2626',
    },
    background: {
      default: '#FAF5FF',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#1E1B4B',
      secondary: '#475569',
    },
    divider: '#DDD6FE',
  },
  typography: {
    fontFamily: 'Vazirmatn, Tahoma, sans-serif',
    fontSize: 14,
    body1: {
      lineHeight: 1.8,
    },
    body2: {
      lineHeight: 1.8,
    },
  },
  shape: {
    borderRadius: 12,
  },
  transitions: {
    duration: {
      shortest: 150,
      shorter: 200,
      short: 250,
      standard: 250,
      complex: 250,
      enteringScreen: 225,
      leavingScreen: 195,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          minHeight: 44,
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        '@media (prefers-reduced-motion: reduce)': {
          '*, *::before, *::after': {
            animationDuration: '0.01ms !important',
            animationIterationCount: '1 !important',
            transitionDuration: '0.01ms !important',
            scrollBehavior: 'auto !important',
          },
        },
      },
    },
  },
})
