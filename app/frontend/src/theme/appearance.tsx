import {useEffect, useMemo, useState} from 'react';

export type ThemeMode = 'system' | 'light' | 'dark';
export type PaletteId = 'terminal' | 'orange' | 'blue' | 'violet' | 'teal' | 'magenta' | 'custom';
export type Density = 'comfortable' | 'compact';
export type MotionMode = 'system' | 'reduce';

export type CustomPalette = {accent: string; accent2: string; bg: string; surface: string; text: string};
export type CustomPair = {light: CustomPalette; dark: CustomPalette};

export type Preferences = {
  theme: ThemeMode;
  palette: PaletteId;
  custom: CustomPair;
  motion: MotionMode;
  density: Density;
  fullCoverage: boolean;
  sampleDetails: boolean;
  methodNotes: boolean;
  qualityLabels: boolean;
  technicalDetails: boolean;
  moduleStatus: boolean;
};

export const defaultCustom: CustomPair = {
  light: {accent: '#2563eb', accent2: '#ea580c', bg: '#f8fafc', surface: '#ffffff', text: '#0f172a'},
  dark: {accent: '#7aa2ff', accent2: '#ff9a62', bg: '#0b1020', surface: '#141b2c', text: '#eef2ff'},
};

export const defaults: Preferences = {
  theme: 'system',
  palette: 'terminal',
  custom: defaultCustom,
  motion: 'system',
  density: 'comfortable',
  fullCoverage: false,
  sampleDetails: false,
  methodNotes: false,
  qualityLabels: false,
  technicalDetails: false,
  moduleStatus: false,
};

export const PALETTES: {id: PaletteId; name: string; tagline: string; light: {accent: string; accent2: string; bg: string}; dark: {accent: string; accent2: string; bg: string}}[] = [
  {id: 'terminal', name: '战术终端', tagline: '黑白工业 · 信号黄', light: {accent: '#e4e928', accent2: '#3959bc', bg: '#eeefeb'}, dark: {accent: '#e4e928', accent2: '#8ba8ff', bg: '#141615'}},
  {id: 'orange', name: '橙色', tagline: '白底鲜橙 · 深蓝对比', light: {accent: '#e85d04', accent2: '#1d4e89', bg: '#faf7f2'}, dark: {accent: '#ff8a3d', accent2: '#8ab4ff', bg: '#0f0c09'}},
  {id: 'blue', name: '蓝色', tagline: '钴蓝 · 珊瑚橙', light: {accent: '#2449d8', accent2: '#f0642d', bg: '#f3f6fd'}, dark: {accent: '#7f9dff', accent2: '#ff8b60', bg: '#080d16'}},
  {id: 'violet', name: '紫色', tagline: '紫罗兰 · 亮黄', light: {accent: '#6633e0', accent2: '#a86b00', bg: '#f7f4fe'}, dark: {accent: '#a78bff', accent2: '#ffd34d', bg: '#0d0a15'}},
  {id: 'teal', name: '青色', tagline: '青绿 · 珊瑚红', light: {accent: '#0a8577', accent2: '#cf4530', bg: '#f1faf7'}, dark: {accent: '#3fd6c4', accent2: '#ff8a70', bg: '#07120f'}},
  {id: 'magenta', name: '洋红色', tagline: '洋红 · 冰青', light: {accent: '#c01a6c', accent2: '#0a6f7c', bg: '#fdf5fa'}, dark: {accent: '#ff6aac', accent2: '#64e3ef', bg: '#120811'}},
];

const storageKey = 'demo-lab.appearance.v2';
const legacyKey = 'demo-lab.appearance.v1';

export function normalizeHex(input: string): string | null {
  const raw = String(input || '').trim().replace(/^#/, '');
  if (/^[0-9a-fA-F]{3}$/.test(raw)) return '#' + raw.split('').map(c => c + c).join('').toLowerCase();
  if (/^[0-9a-fA-F]{6}$/.test(raw)) return '#' + raw.toLowerCase();
  return null;
}

function hexToRgb(hex: string): [number, number, number] {
  const value = normalizeHex(hex) || '#000000';
  return [parseInt(value.slice(1, 3), 16), parseInt(value.slice(3, 5), 16), parseInt(value.slice(5, 7), 16)];
}
function rgbToHex(rgb: [number, number, number]): string {
  return '#' + rgb.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
}
function channel(v: number): number {
  const s = v / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}
export function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}
export function contrastRatio(a: string, b: string): number {
  const la = luminance(a), lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
export function readInk(background: string): string {
  return contrastRatio('#ffffff', background) >= contrastRatio('#111111', background) ? '#ffffff' : '#111111';
}
function mix(a: string, b: string, weight: number): string {
  const [r1, g1, b1] = hexToRgb(a), [r2, g2, b2] = hexToRgb(b);
  return rgbToHex([r1 + (r2 - r1) * weight, g1 + (g2 - g1) * weight, b1 + (b2 - b1) * weight]);
}
function towardsContrast(colour: string, background: string, minimum: number): string {
  if (contrastRatio(colour, background) >= minimum) return colour;
  const dark = luminance(background) > 0.4;
  for (let i = 1; i <= 20; i++) {
    const candidate = mix(colour, dark ? '#000000' : '#ffffff', i * 0.05);
    if (contrastRatio(candidate, background) >= minimum) return candidate;
  }
  return dark ? '#000000' : '#ffffff';
}

export type ContrastReport = {accentOnSurface: number; accentOnBg: number; textOnBg: number; textOnSurface: number; accent2OnSurface: number; warnings: string[]};

export function contrastReport(p: CustomPalette): ContrastReport {
  const values = {
    accentOnSurface: contrastRatio(p.accent, p.surface),
    accentOnBg: contrastRatio(p.accent, p.bg),
    textOnBg: contrastRatio(p.text, p.bg),
    textOnSurface: contrastRatio(p.text, p.surface),
    accent2OnSurface: contrastRatio(p.accent2, p.surface),
  };
  const warnings: string[] = [];
  if (values.textOnBg < 4.5) warnings.push('正文与页面底色的对比度低于 4.5:1，长文阅读会吃力。');
  if (values.accentOnSurface < 3) warnings.push('主色与卡片底色的对比度低于 3:1，按钮和焦点框可能不够清楚。');
  if (values.accent2OnSurface < 3) warnings.push('对比色与卡片底色的对比度低于 3:1。');
  return {...values, warnings};
}

export function autoFixPalette(p: CustomPalette): CustomPalette {
  const bg = normalizeHex(p.bg) || p.bg;
  const surface = normalizeHex(p.surface) || p.surface;
  const text = towardsContrast(normalizeHex(p.text) || p.text, bg, 4.5);
  const accent = towardsContrast(normalizeHex(p.accent) || p.accent, surface, 3);
  const accent2 = towardsContrast(normalizeHex(p.accent2) || p.accent2, surface, 3);
  return {accent, accent2, bg, surface, text};
}

function cleanPalette(value: any, fallback: CustomPalette): CustomPalette {
  const read = (key: keyof CustomPalette) => normalizeHex(value && value[key]) || fallback[key];
  return {accent: read('accent'), accent2: read('accent2'), bg: read('bg'), surface: read('surface'), text: read('text')};
}

function cleanCustom(value: any): CustomPair {
  return {
    light: cleanPalette(value && value.light, defaultCustom.light),
    dark: cleanPalette(value && value.dark, defaultCustom.dark),
  };
}

function initialPreferences(): Preferences {
  const clean: Preferences = {...defaults, custom: {light: {...defaultCustom.light}, dark: {...defaultCustom.dark}}};
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    const legacy = saved ? null : JSON.parse(localStorage.getItem(legacyKey) || 'null');
    const source = saved || legacy || {};
    for (const key of ['fullCoverage', 'sampleDetails', 'methodNotes', 'qualityLabels', 'technicalDetails', 'moduleStatus'] as const) {
      if (typeof source[key] === 'boolean') clean[key] = source[key];
    }
    if (['system', 'light', 'dark'].includes(source.theme)) clean.theme = source.theme;
    if (['comfortable', 'compact'].includes(source.density)) clean.density = source.density;
    if (['system', 'reduce'].includes(source.motion)) clean.motion = source.motion;
    if (['terminal', 'orange', 'blue', 'violet', 'teal', 'magenta', 'custom'].includes(source.palette)) clean.palette = source.palette;
    if (saved && saved.custom) clean.custom = cleanCustom(saved.custom);
  } catch {
    /* localStorage can be disabled; defaults still work. */
  }
  try {
    const query = new URLSearchParams(window.location.search);
    const theme = query.get('theme');
    const palette = query.get('palette');
    if (theme === 'light' || theme === 'dark' || theme === 'system') clean.theme = theme;
    if (palette === 'terminal' || palette === 'orange' || palette === 'blue' || palette === 'violet' || palette === 'teal' || palette === 'magenta' || palette === 'custom') clean.palette = palette;
    if (query.get('motion') === 'reduce') clean.motion = 'reduce';
    if (query.get('density') === 'compact') clean.density = 'compact';
  } catch {
    /* Query preview is optional. */
  }
  return clean;
}

function writeCustomVars(palette: CustomPalette, theme: 'light' | 'dark') {
  const html = document.documentElement;
  const accent = normalizeHex(palette.accent) || palette.accent;
  const accent2 = normalizeHex(palette.accent2) || palette.accent2;
  const bg = normalizeHex(palette.bg) || palette.bg;
  const surface = normalizeHex(palette.surface) || palette.surface;
  const text = normalizeHex(palette.text) || palette.text;
  html.style.setProperty('--accent', accent);
  html.style.setProperty('--accent-2', accent2);
  html.style.setProperty('--bg', bg);
  html.style.setProperty('--surface', surface);
  html.style.setProperty('--text', text);
  const ink = readInk(accent);
  html.style.setProperty('--accent-contrast', ink);
  html.style.setProperty('--custom-accent-ink', ink);
  html.style.setProperty('--custom-theme', theme);
}
function clearCustomVars() {
  const html = document.documentElement;
  for (const key of ['--accent', '--accent-2', '--bg', '--surface', '--text', '--accent-contrast', '--custom-accent-ink', '--custom-theme']) {
    html.style.removeProperty(key);
  }
}

export type AppearanceState = {
  prefs: Preferences;
  setPrefs: (next: Preferences) => void;
  preview: Preferences | null;
  setPreview: (next: Preferences | null) => void;
  resolvedTheme: 'light' | 'dark';
  reducedMotion: boolean;
};

export function useAppearance(): AppearanceState {
  const [prefs, setPrefs] = useState<Preferences>(initialPreferences);
  const [preview, setPreview] = useState<Preferences | null>(null);
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');
  const [reducedMotion, setReducedMotion] = useState(false);
  const applied = preview || prefs;

  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    const apply = () => {
      const theme: 'light' | 'dark' = applied.theme === 'system' ? (system.matches ? 'dark' : 'light') : applied.theme;
      const motion = applied.motion === 'reduce' || reduce.matches;
      const html = document.documentElement;
      html.dataset.theme = theme;
      html.dataset.palette = applied.palette;
      html.dataset.density = applied.density;
      html.dataset.glass = 'static';
      html.dataset.motion = motion ? 'reduce' : 'full';
      if (applied.palette === 'custom') writeCustomVars(applied.custom[theme], theme);
      else clearCustomVars();
      setResolvedTheme(theme);
      setReducedMotion(motion);
    };
    apply();
    system.addEventListener('change', apply);
    reduce.addEventListener('change', apply);
    return () => {
      system.removeEventListener('change', apply);
      reduce.removeEventListener('change', apply);
    };
  }, [applied]);

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(prefs));
    } catch {
      /* Display still works when storage is disabled. */
    }
  }, [prefs]);

  const setPrefsStable = useMemo(() => (next: Preferences) => setPrefs(next), []);
  return {prefs, setPrefs: setPrefsStable, preview, setPreview, resolvedTheme, reducedMotion};
}

