import React, {useEffect, useState} from 'react';

export const defaults = {
  theme: 'system' as 'system' | 'light' | 'dark',
  density: 'comfortable' as 'comfortable' | 'compact',
  fullCoverage: false,
  sampleDetails: false,
  methodNotes: false,
  qualityLabels: false,
  technicalDetails: false,
  moduleStatus: false,
};
export type Preferences = typeof defaults;
const storageKey = 'demo-lab.appearance.v1';

export function useAppearance() {
  const [prefs, setPrefs] = useState<Preferences>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
      const clean = {...defaults};
      for (const key of Object.keys(defaults) as (keyof Preferences)[]) {
        if (typeof defaults[key] === 'boolean' && typeof saved?.[key] === 'boolean')
          Object.assign(clean, {[key]: saved[key]});
      }
      if (['system', 'light', 'dark'].includes(saved?.theme)) clean.theme = saved.theme;
      if (['comfortable', 'compact'].includes(saved?.density)) clean.density = saved.density;
      return clean;
    } catch { return {...defaults}; }
  });
  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      document.documentElement.dataset.theme = prefs.theme === 'system' ? (system.matches ? 'dark' : 'light') : prefs.theme;
      document.documentElement.dataset.density = prefs.density;
    };
    apply();
    system.addEventListener('change', apply);
    try { localStorage.setItem(storageKey, JSON.stringify(prefs)); } catch { /* Display still works when storage is disabled. */ }
    return () => system.removeEventListener('change', apply);
  }, [prefs]);
  return [prefs, setPrefs] as const;
}

const switches: [keyof Preferences, string, string][] = [
  ['fullCoverage', '显示 100% 覆盖率', '覆盖不足与覆盖未知始终显示'],
  ['sampleDetails', '样本明细', '显示分子、分母、未知数与排除数'],
  ['methodNotes', '方法长说明', '展开模块方法和证据筛选说明'],
  ['qualityLabels', '全部质量标签', '显示观测、计算标签与单位；估计和不可用始终保留'],
  ['technicalDetails', '技术详情', '显示 SteamID、版本、缓存、耗时和参数快照'],
  ['moduleStatus', '模块状态总览', '额外显示各模块状态快捷入口'],
];
export function AppearanceSettings({prefs, onChange, onClose}: {prefs: Preferences; onChange: (p: Preferences) => void; onClose: () => void}) {
  return <section className="panel appearance-panel" aria-label="显示设置" id="appearance-settings">
    <div className="row"><div><h2>显示设置</h2><p className="muted">偏好自动保存在当前浏览器，仅调整显示。</p></div><button onClick={onClose}>收起设置</button></div>
    <div className="appearance-top"><fieldset><legend>界面主题</legend><div className="segmented">{(['system','light','dark'] as const).map((theme, i) => <button key={theme} aria-pressed={prefs.theme === theme} onClick={() => onChange({...prefs, theme})}>{['跟随系统','浅色','深色'][i]}</button>)}</div></fieldset>
    <label>信息密度<select value={prefs.density} onChange={e => onChange({...prefs, density: e.target.value as Preferences['density']})}><option value="comfortable">舒适</option><option value="compact">紧凑</option></select></label></div>
    <div className="appearance-switches">{switches.map(([key,label,hint]) => <label className="setting-toggle" key={key}><input type="checkbox" checked={Boolean(prefs[key])} onChange={e => onChange({...prefs,[key]: e.target.checked})}/><span>{label}<small>{hint}</small></span></label>)}</div>
    <button className="reset-appearance" onClick={() => onChange({...defaults})}>恢复默认显示</button>
  </section>;
}

export function coverageText(coverage: unknown) {
  if (typeof coverage !== 'number' || !Number.isFinite(coverage)) return '覆盖率未知';
  const percentage = coverage * 100;
  return `覆盖 ${coverage < 1 && percentage >= 99.95 ? '<100' : percentage.toLocaleString('zh-CN', {maximumFractionDigits: 1})}%`;
}
export function Coverage({value, showFull, bar = false}: {value: unknown; showFull: boolean; bar?: boolean}) {
  if (value === 1 && !showFull) return null;
  return <div className="coverage-summary" title={typeof value === 'number' ? `覆盖率：${value * 100}%` : '没有可用的覆盖率数据'}>
    {bar && typeof value === 'number' && Number.isFinite(value) && <div className="coverage"><i style={{width: `${Math.min(1,Math.max(0,value))*100}%`}}/></div>}
    <small>{coverageText(value)}</small>
  </div>;
}
