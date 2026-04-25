export const themeTokens = {
  colors: {
    primaryNavy: '#1E293B',
    secondaryNavy: '#334155',
    accentTeal: '#0EA5E9',
    background: '#EEF2FF',
    surface: '#FFFFFF',
    textPrimary: '#0F172A',
    textSecondary: '#475569',
    success: '#16A34A',
    warning: '#F59E0B',
    danger: '#DC2626',
    rowHover: '#E0F2FE',
    tableStripe: '#F8FAFC',
    border: '#CBD5E1'
  },
  borderRadius: {
    sm: '8px',
    md: '12px',
    lg: '18px',
    xl: '22px',
    pill: '999px'
  },
  shadows: {
    sm: '0 3px 10px rgba(15, 23, 42, 0.08)',
    md: '0 10px 26px rgba(30, 41, 59, 0.13)',
    lg: '0 18px 40px rgba(30, 41, 59, 0.18)'
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '32px'
  },
  typography: {
    fontFamily: "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    monoFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
    sizes: {
      xs: '12px',
      sm: '14px',
      md: '16px',
      lg: '20px',
      xl: '28px'
    },
    weights: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800
    },
    lineHeights: {
      tight: 1.2,
      normal: 1.5,
      relaxed: 1.65
    }
  }
};

export const cssVarTokens = {
  '--ps-color-primary': themeTokens.colors.primaryNavy,
  '--ps-color-secondary': themeTokens.colors.secondaryNavy,
  '--ps-color-accent': themeTokens.colors.accentTeal,
  '--ps-color-bg': themeTokens.colors.background,
  '--ps-color-surface': themeTokens.colors.surface,
  '--ps-color-text-primary': themeTokens.colors.textPrimary,
  '--ps-color-text-secondary': themeTokens.colors.textSecondary,
  '--ps-color-success': themeTokens.colors.success,
  '--ps-color-warning': themeTokens.colors.warning,
  '--ps-color-danger': themeTokens.colors.danger,
  '--ps-color-row-hover': themeTokens.colors.rowHover,
  '--ps-color-table-stripe': themeTokens.colors.tableStripe,
  '--ps-color-border': themeTokens.colors.border,
  '--ps-radius-sm': themeTokens.borderRadius.sm,
  '--ps-radius-md': themeTokens.borderRadius.md,
  '--ps-radius-lg': themeTokens.borderRadius.lg,
  '--ps-radius-xl': themeTokens.borderRadius.xl,
  '--ps-radius-pill': themeTokens.borderRadius.pill,
  '--ps-shadow-sm': themeTokens.shadows.sm,
  '--ps-shadow-md': themeTokens.shadows.md,
  '--ps-shadow-lg': themeTokens.shadows.lg,
  '--ps-space-xs': themeTokens.spacing.xs,
  '--ps-space-sm': themeTokens.spacing.sm,
  '--ps-space-md': themeTokens.spacing.md,
  '--ps-space-lg': themeTokens.spacing.lg,
  '--ps-space-xl': themeTokens.spacing.xl,
  '--ps-space-2xl': themeTokens.spacing['2xl'],
  '--ps-space-3xl': themeTokens.spacing['3xl'],
  '--ps-font-family': themeTokens.typography.fontFamily,
  '--ps-font-family-mono': themeTokens.typography.monoFamily,
  '--ps-font-size-sm': themeTokens.typography.sizes.sm,
  '--ps-font-size-md': themeTokens.typography.sizes.md,
  '--ps-font-size-lg': themeTokens.typography.sizes.lg,
  '--ps-font-weight-medium': themeTokens.typography.weights.medium,
  '--ps-font-weight-semibold': themeTokens.typography.weights.semibold,
  '--ps-font-weight-bold': themeTokens.typography.weights.bold,
  '--ps-line-height-normal': themeTokens.typography.lineHeights.normal
};
