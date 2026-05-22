import { createLightTheme, type BrandVariants, type Theme } from "@fluentui/react-components";

export const tfColorTokens = {
  appBg: "#f3f5f8",
  workbench: "#eef2f6",
  surface: "#ffffff",
  surfaceAlt: "#f8fafc",
  surfaceMuted: "#f1f4f7",
  surfacePressed: "#e8eef3",
  border: "#d6dee6",
  borderStrong: "#b8c4cf",
  text: "#1f252c",
  textMuted: "#56616d",
  textSubtle: "#737f8c",
  brand: "#256f68",
  brandHover: "#1d5a55",
  brandPressed: "#164742",
  brandSubtle: "#e3f3f0",
  brandSubtleHover: "#d4ece8",
  success: "#18705a",
  successBg: "#e7f5ef",
  warning: "#8a6416",
  warningBg: "#fff7e1",
  danger: "#a6404f",
  dangerBg: "#fff1f3"
} as const;

export const tfRadiusTokens = {
  xs: "4px",
  sm: "6px",
  md: "8px",
  lg: "10px",
  xl: "12px"
} as const;

export const tfShadowTokens = {
  none: "none",
  xs: "0 1px 2px rgba(31, 37, 44, 0.08)",
  sm: "0 2px 8px rgba(31, 37, 44, 0.10)",
  md: "0 8px 24px rgba(31, 37, 44, 0.12)"
} as const;

export const textFlowCssVariables = {
  "--tf-color-app-bg": tfColorTokens.appBg,
  "--tf-color-workbench": tfColorTokens.workbench,
  "--tf-color-surface": tfColorTokens.surface,
  "--tf-color-surface-alt": tfColorTokens.surfaceAlt,
  "--tf-color-surface-muted": tfColorTokens.surfaceMuted,
  "--tf-color-surface-pressed": tfColorTokens.surfacePressed,
  "--tf-color-border": tfColorTokens.border,
  "--tf-color-border-strong": tfColorTokens.borderStrong,
  "--tf-color-text": tfColorTokens.text,
  "--tf-color-text-muted": tfColorTokens.textMuted,
  "--tf-color-text-subtle": tfColorTokens.textSubtle,
  "--tf-color-brand": tfColorTokens.brand,
  "--tf-color-brand-hover": tfColorTokens.brandHover,
  "--tf-color-brand-pressed": tfColorTokens.brandPressed,
  "--tf-color-brand-subtle": tfColorTokens.brandSubtle,
  "--tf-color-brand-subtle-hover": tfColorTokens.brandSubtleHover,
  "--tf-color-success": tfColorTokens.success,
  "--tf-color-success-bg": tfColorTokens.successBg,
  "--tf-color-warning": tfColorTokens.warning,
  "--tf-color-warning-bg": tfColorTokens.warningBg,
  "--tf-color-danger": tfColorTokens.danger,
  "--tf-color-danger-bg": tfColorTokens.dangerBg,
  "--tf-radius-xs": tfRadiusTokens.xs,
  "--tf-radius-sm": tfRadiusTokens.sm,
  "--tf-radius-md": tfRadiusTokens.md,
  "--tf-radius-lg": tfRadiusTokens.lg,
  "--tf-radius-xl": tfRadiusTokens.xl,
  "--tf-shadow-none": tfShadowTokens.none,
  "--tf-shadow-xs": tfShadowTokens.xs,
  "--tf-shadow-sm": tfShadowTokens.sm,
  "--tf-shadow-md": tfShadowTokens.md
} as const;

const textFlowBrand: BrandVariants = {
  10: "#061716",
  20: "#0b2523",
  30: "#103532",
  40: "#164742",
  50: "#1d5a55",
  60: "#256f68",
  70: "#31877f",
  80: "#43a198",
  90: "#5abbb1",
  100: "#78d1c7",
  110: "#99e0d8",
  120: "#b7ece6",
  130: "#d2f5f1",
  140: "#e4faf7",
  150: "#f0fdfb",
  160: "#f8fffd"
};

export const textFlowFluentTheme: Theme = {
  ...createLightTheme(textFlowBrand),
  colorNeutralBackground1: "var(--tf-color-surface)",
  colorNeutralBackground1Hover: "var(--tf-color-surface-alt)",
  colorNeutralBackground1Pressed: "var(--tf-color-surface-pressed)",
  colorNeutralBackground2: "var(--tf-color-surface-alt)",
  colorNeutralBackground2Hover: "var(--tf-color-surface-muted)",
  colorNeutralBackground2Pressed: "var(--tf-color-surface-pressed)",
  colorNeutralBackground3: "var(--tf-color-surface-muted)",
  colorNeutralBackground4: "var(--tf-color-app-bg)",
  colorNeutralForeground1: "var(--tf-color-text)",
  colorNeutralForeground2: "var(--tf-color-text-muted)",
  colorNeutralForeground3: "var(--tf-color-text-subtle)",
  colorNeutralStroke1: "var(--tf-color-border)",
  colorNeutralStroke1Hover: "var(--tf-color-border-strong)",
  colorNeutralStroke2: "var(--tf-color-border)",
  colorBrandBackground: "var(--tf-color-brand)",
  colorBrandBackgroundHover: "var(--tf-color-brand-hover)",
  colorBrandBackgroundPressed: "var(--tf-color-brand-pressed)",
  colorBrandBackground2: "var(--tf-color-brand-subtle)",
  colorBrandForeground1: "var(--tf-color-brand-pressed)",
  colorCompoundBrandForeground1: "var(--tf-color-brand)",
  colorCompoundBrandForeground1Hover: "var(--tf-color-brand-hover)",
  fontFamilyBase: "\"IBM Plex Sans\", \"Segoe UI\", sans-serif",
  fontFamilyMonospace: "\"Cascadia Code\", \"SFMono-Regular\", Consolas, monospace",
  borderRadiusSmall: "var(--tf-radius-sm)",
  borderRadiusMedium: "var(--tf-radius-md)",
  borderRadiusLarge: "var(--tf-radius-lg)",
  borderRadiusXLarge: "var(--tf-radius-xl)",
  shadow2: "var(--tf-shadow-xs)",
  shadow4: "var(--tf-shadow-sm)",
  shadow8: "var(--tf-shadow-sm)",
  shadow16: "var(--tf-shadow-md)"
};
