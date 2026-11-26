import { createTheme } from '@mui/material/styles'

/** Formal navy — B2B / government-style palette (ui-ux-pro-max). */
export const theme = createTheme({
  direction: 'rtl',
  palette: {
    primary: {
      main: '#1E3A5F',
      dark: '#0F2942',
      light: '#2E4A6F',
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: '#0369A1',
      contrastText: '#FFFFFF',
    },
    error: {
      main: '#DC2626',
    },
    warning: {
      main: '#B45309',
    },
    info: {
      main: '#0369A1',
    },
    success: {
      main: '#047857',
    },
    background: {
      default: '#F8FAFC',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#0F172A',
      secondary: '#475569',
    },
    divider: '#E2E8F0',
    action: {
      hover: 'rgba(30, 58, 95, 0.06)',
      selected: 'rgba(30, 58, 95, 0.10)',
    },
  },
  typography: {
    fontFamily: 'Vazirmatn, Tahoma, sans-serif',
    fontSize: 14,
    h6: {
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    body1: {
      lineHeight: 1.8,
    },
    body2: {
      lineHeight: 1.8,
    },
    button: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
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
          borderRadius: 8,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
        label: {
          whiteSpace: 'nowrap',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: '#1E3A5F',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#F8FAFC',
        },
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
