import type { ComponentProps } from 'react';
import type Ionicons from '@expo/vector-icons/Ionicons';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export interface Palette {
  bg: string;
  card: string;
  cardAlt: string;
  border: string;
  text: string;
  textSecondary: string;
  teal: string;
  blue: string;
  onAccent: string;
  green: string;
  amber: string;
  red: string;
  neutral: string;
  overlay: string;
  gradient: [string, string];
}

export const dark: Palette = {
  bg: '#0B1020',
  card: '#151D30',
  cardAlt: '#1C2640',
  border: '#27324F',
  text: '#F1F5F9',
  textSecondary: '#A8B3C9',
  teal: '#2DD4BF',
  blue: '#60A5FA',
  onAccent: '#06201D',
  green: '#34D399',
  amber: '#FBBF24',
  red: '#F87171',
  neutral: '#93A3BF',
  overlay: 'rgba(5,8,18,0.72)',
  gradient: ['#2DD4BF', '#60A5FA'],
};

export const light: Palette = {
  bg: '#F3F6FB',
  card: '#FFFFFF',
  cardAlt: '#EAF0F8',
  border: '#D6DFEB',
  text: '#0B1020',
  textSecondary: '#4B5872',
  teal: '#0D9488',
  blue: '#2563EB',
  onAccent: '#FFFFFF',
  green: '#047857',
  amber: '#B45309',
  red: '#B91C1C',
  neutral: '#56637D',
  overlay: 'rgba(11,16,32,0.55)',
  gradient: ['#0D9488', '#2563EB'],
};

// 8 px spacing grid
export const space = { xs: 4, s: 8, m: 16, l: 24, xl: 32, xxl: 48 } as const;
export const radius = { s: 12, m: 20, l: 24, pill: 999 } as const;
export const touch = 48; // minimum comfortable hit target (dp)

export const font = {
  h1: { fontSize: 28, fontWeight: '800' as const, lineHeight: 34 },
  h2: { fontSize: 22, fontWeight: '700' as const, lineHeight: 28 },
  h3: { fontSize: 17, fontWeight: '700' as const, lineHeight: 22 },
  body: { fontSize: 15, fontWeight: '400' as const, lineHeight: 21 },
  small: { fontSize: 13, fontWeight: '400' as const, lineHeight: 18 },
  label: { fontSize: 13, fontWeight: '600' as const, lineHeight: 18 },
};

export type Category = 'low' | 'suspicious' | 'high' | 'insufficient';

export function riskMeta(c: Palette, category: Category | string | null | undefined): { color: string; icon: IconName } {
  switch (category) {
    case 'low':
      return { color: c.green, icon: 'shield-checkmark' };
    case 'suspicious':
      return { color: c.amber, icon: 'alert-circle' };
    case 'high':
      return { color: c.red, icon: 'warning' };
    default:
      return { color: c.neutral, icon: 'help-circle' };
  }
}

export function severityColor(c: Palette, severity: string): string {
  return severity === 'high' ? c.red : severity === 'medium' ? c.amber : severity === 'low' ? c.blue : c.green;
}
