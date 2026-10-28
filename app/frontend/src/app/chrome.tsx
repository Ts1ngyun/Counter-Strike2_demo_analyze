import {BackgroundPanel} from '../theme/Background';
import React, {useEffect, useState} from 'react';
import Icon, {type IconName} from '../ui/Icon';
import {Field, Modal, Segmented} from '../ui/primitives';
import {PARAM_NAMES} from '../explain/MetricExplain';
import type {Obj} from '../app/format';
import {
  autoFixPalette, contrastReport, defaultCustom, defaults, normalizeHex, PALETTES,
  type CustomPair, type PaletteId, type Preferences,
} from '../theme/appearance';
import './chrome.css';

export type Tab = 'overview' | 'analysis' | 'replay' | 'profiles' | 'jobs';

const NAV: {id: Tab; label: string; hint: string; icon: IconName}[] = [
  {id: 'overview', label: '概览', hint: '比分、回合与队列', icon: 'grid'},
  {id: 'analysis', label: '比赛分析', hint: '指标与证据', icon: 'pulse'},
  {id: 'replay', label: '2D 回放', hint: '位置、书签与画线', icon: 'play'},
  {id: 'profiles', label: '个人存档', hint: '多 ID 与跨场趋势', icon: 'archive'},
  {id: 'jobs', label: '任务与数据', hint: '队列、汇总与存储', icon: 'stack'},
];

export function Sidebar({tab, onSelect, moduleTitle, paletteName, onAppearance, localOnly = true}: {
  tab: Tab;
  onSelect: (tab: Tab) => void;
  moduleTitle?: string;
  paletteName: string;
  onAppearance: () => void;
  localOnly?: boolean;
}) {
  return (
    <aside className="sidebar glass" aria-label="主导航区">
      <div className="brand">
        <span className="brand-mark"><Icon name="spark" size={22} /></span>
        <div className="brand-text">
          <strong>DEMO LAB</strong>
          <span>战术复盘 / 本地分析</span>
        </div>
      </div>
      <nav aria-label="主导航">
        <span className="nav-label">WORKSPACE / 工作区</span>
        {NAV.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={'nav-item' + (tab === item.id ? ' selected' : '')}
            aria-current={tab === item.id ? 'page' : undefined}
            onClick={() => onSelect(item.id)}
          >
            <span className="nav-index" aria-hidden="true">0{index + 1}</span><span className="nav-icon"><Icon name={item.icon} size={18} /></span>
            <span className="nav-copy">
              <span className="nav-title">{item.label}</span>
              <small>{item.id === 'analysis' && moduleTitle ? moduleTitle : item.hint}</small>
            </span>
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        {localOnly && (
          <div className="local-note">
            <span className="live-dot" aria-hidden="true" />
            <div><strong>仅在本机运行</strong><small>不上传云端 · 分析时可离线</small></div>
          </div>
        )}
        <button type="button" className="theme-button" onClick={onAppearance} aria-label="主题与显示" aria-haspopup="dialog">
          <span><strong>主题与显示</strong><small>{paletteName} · 明暗 / 自定义</small></span>
          <Icon name="sliders" size={16} />
        </button>
      </div>
    </aside>
  );
}

export function TopBar({title, eyebrow, children}: {title: React.ReactNode; eyebrow?: React.ReactNode; children?: React.ReactNode}) {
  return (
    <header className="topbar">
      <div className="page-heading">
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
      </div>
      <div className="topbar-actions">{children}</div>
    </header>
  );
}

const themeOptions = [
  {value: 'light', label: '明亮', icon: 'sun' as IconName},
  {value: 'dark', label: '暗黑', icon: 'moon' as IconName},
  {value: 'system', label: '跟随系统', icon: 'monitor' as IconName},
];
const motionOptions = [
  {value: 'system', label: '跟随系统'},
  {value: 'reduce', label: '减少动效'},
];
const densityOptions = [
  {value: 'comfortable', label: '舒适'},
  {value: 'compact', label: '紧凑'},
];

const displaySwitches: {key: keyof Preferences; label: string; hint: string}[] = [
  {key: 'fullCoverage', label: '显示全部覆盖率', hint: '100% 覆盖率默认隐藏，避免每张卡都重复一遍。'},
  {key: 'sampleDetails', label: '显示样本明细', hint: '显示分子、分母、未知数与排除数。'},
  {key: 'methodNotes', label: '显示方法说明', hint: '展开模块的算法说明与使用边界。'},
  {key: 'qualityLabels', label: '显示全部质量标签', hint: '估计值与不可用始终保留，开启后连“计算得出”也标出。'},
  {key: 'technicalDetails', label: '显示技术信息', hint: 'SteamID、版本、耗时、参数与原始证据。'},
  {key: 'moduleStatus', label: '显示模块状态条', hint: '在分析页底部增加各模块状态快捷入口。'},
];

const colorLabels: {key: keyof CustomPair['light']; label: string; hint: string}[] = [
  {key: 'accent', label: '主色', hint: '按钮、选中项、图表主线与焦点框。'},
  {key: 'accent2', label: '对比色', hint: '次要图表、标签和高亮，不要与主色过近。'},
  {key: 'bg', label: '页面底色', hint: '整页背景。'},
  {key: 'surface', label: '卡片底色', hint: '卡片、面板与弹层的主体颜色。'},
  {key: 'text', label: '文字颜色', hint: '正文和标题；工具会自动派生次要文字。'},
];

export function AppearancePanel({open, prefs, resolvedTheme, onChange, onPreview, onClose}: {
  open: boolean;
  prefs: Preferences;
  resolvedTheme: 'light' | 'dark';
  onChange: (next: Preferences) => void;
  onPreview: (next: Preferences | null) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<CustomPair>(prefs.custom);
  const [editMode, setEditMode] = useState<'light' | 'dark'>(resolvedTheme);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (open) {
      setDraft(prefs.custom);
      setEditMode(resolvedTheme);
      setMessage('');
    }
  }, [open, prefs.custom, resolvedTheme]);

  useEffect(() => { setEditMode(resolvedTheme); }, [resolvedTheme]);

  const commit = (next: Preferences) => { onPreview(null); onChange(next); };
  const palette = draft[editMode];
  const validFields = colorLabels.filter(item => !normalizeHex(palette[item.key]));
  const valid = validFields.length === 0;
  const report = contrastReport(palette);

  function applyDraft(next: CustomPair) {
    setDraft(next);
    setMessage('');
    if (colorLabels.every(item => normalizeHex(next[editMode][item.key]))) {
      onPreview({...prefs, palette: 'custom', custom: next});
    }
  }

  function setColor(key: keyof CustomPair['light'], value: string) {
    applyDraft({...draft, [editMode]: {...draft[editMode], [key]: value}});
  }

  function saveCustom() {
    if (!valid) { setMessage('还有颜色格式不正确，修正后再保存。'); return; }
    const next = {...prefs, palette: 'custom' as PaletteId, custom: draft};
    onPreview(null);
    onChange(next);
    setMessage('已保存。浅色与深色配置会分别记住。');
  }

  function resetCustom() {
    setDraft(defaultCustom);
    applyDraft(defaultCustom);
    setMessage('自定义颜色已恢复为默认值，保存后生效。');
  }

  function resetAll() {
    setDraft(defaultCustom);
    commit({...defaults, custom: defaultCustom});
    setMessage('已恢复全部默认设置。');
  }

  const activePalette = prefs.palette;

  return (
    <Modal open={open} onClose={() => {onPreview(null); onClose();}} title="主题与显示" eyebrow="APPEARANCE" label="主题与显示设置" side size="lg"
      footer={<div className="appearance-foot"><button type="button" onClick={resetAll}>恢复全部默认</button><span className="muted">偏好只保存在当前浏览器。</span><button type="button" className="primary" onClick={() => {onPreview(null); onClose();}}>完成</button></div>}>
      <div className="appearance-sheet">
        <BackgroundPanel />
        <section className="settings-section">
          <div className="settings-heading"><h3>明暗模式</h3><small>跟随系统会随电脑外观自动切换。</small></div>
          <Segmented label="明暗模式" value={prefs.theme} options={themeOptions} onChange={value => commit({...prefs, theme: value as Preferences['theme']})} />
        </section>

        <section className="settings-section">
          <div className="settings-heading"><h3>配色主题</h3><small>六套预设，每套都有明暗版本。</small></div>
          <div className="palette-grid" role="group" aria-label="配色主题">
            {PALETTES.map(item => {
              return (
                <button key={item.id} type="button" className={'palette-card' + (activePalette === item.id ? ' selected' : '')} aria-pressed={activePalette === item.id} onClick={() => commit({...prefs, palette: item.id})}>
                  <span className="palette-name">{item.name}</span>
                  {activePalette === item.id && <span className="palette-check"><Icon name="check" size={13} /></span>}
                </button>
              );
            })}
            <button type="button" className={'palette-card custom' + (activePalette === 'custom' ? ' selected' : '')} aria-pressed={activePalette === 'custom'} onClick={() => commit({...prefs, palette: 'custom'})}>
              <span className="palette-name">自定义</span>
              {activePalette === 'custom' && <span className="palette-check"><Icon name="check" size={13} /></span>}
            </button>
          </div>
        </section>

        <section className="settings-section custom-editor">
          <div className="settings-heading">
            <h3>自定义颜色</h3>
            <small>浅色和暗色分别保存；编辑时如果当前不是该模式，切换明暗即可预览。</small>
          </div>
          <Segmented label="编辑浅色或深色配置" value={editMode} options={[{value: 'light', label: '浅色配置'}, {value: 'dark', label: '深色配置'}]} onChange={value => setEditMode(value as 'light' | 'dark')} />
          <div className="color-rows">
            {colorLabels.map(item => {
              const value = palette[item.key];
              const invalid = !normalizeHex(value);
              return (
                <div className={'color-row' + (invalid ? ' invalid' : '')} key={item.key}>
                  <div className="color-meta"><strong>{item.label}</strong><small>{item.hint}</small></div>
                  <input type="color" aria-label={item.label + ' 色盘'} value={normalizeHex(value) || '#000000'} onChange={event => setColor(item.key, event.target.value)} />
                  <input className="color-text" aria-label={item.label + ' 十六进制值'} value={value} maxLength={7} spellCheck={false} onChange={event => setColor(item.key, event.target.value)} placeholder="#RRGGBB" />
                </div>
              );
            })}
          </div>
          <div className={'contrast-box' + (report.warnings.length ? ' warn' : '')}>
            <div className="contrast-head"><strong>对比度检查</strong><span>{report.warnings.length ? '存在可读性风险' : '主要组合可读'}</span></div>
            <div className="contrast-grid">
              <span>文字 / 底色 <b className={report.textOnBg < 4.5 ? 'danger-text' : 'ok-text'}>{report.textOnBg.toFixed(1)}:1</b></span>
              <span>主色 / 卡片 <b className={report.accentOnSurface < 3 ? 'danger-text' : 'ok-text'}>{report.accentOnSurface.toFixed(1)}:1</b></span>
              <span>对比色 / 卡片 <b className={report.accent2OnSurface < 3 ? 'danger-text' : 'ok-text'}>{report.accent2OnSurface.toFixed(1)}:1</b></span>
            </div>
            {report.warnings.map(text => <p key={text} className="contrast-warning">{text}</p>)}
            <div className="contrast-actions">
              <button type="button" onClick={() => applyDraft({...draft, [editMode]: autoFixPalette(palette)})}>自动修正对比度</button>
              <button type="button" onClick={resetCustom}>恢复默认颜色</button>
            </div>
          </div>
          {validFields.length > 0 && <p className="form-error" role="alert">这些颜色不是合法的十六进制：{validFields.map(item => item.label).join('、')}。格式示例 #e85d04。</p>}
          {message && <p className="form-ok" role="status">{message}</p>}
          <div className="custom-actions">
            <button type="button" className="primary" disabled={!valid} onClick={saveCustom}>保存自定义配色</button>
            <button type="button" onClick={() => {onPreview(null); setDraft(prefs.custom);}}>放弃未保存修改</button>
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-heading"><h3>阅读与效果</h3><small>默认使用静态磨砂外观，不实时模糊背景。</small></div>
          <div className="settings-inline">
            <Field label="动态效果"><Segmented label="动态效果" value={prefs.motion} options={motionOptions} onChange={value => commit({...prefs, motion: value as Preferences['motion']})} /></Field>
            <Field label="信息密度"><Segmented label="信息密度" value={prefs.density} options={densityOptions} onChange={value => commit({...prefs, density: value as Preferences['density']})} /></Field>
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-heading"><h3>数据展示</h3><small>默认优先显示对复盘有用的信息；不确定性始终保留。</small></div>
          <div className="switch-grid">
            {displaySwitches.map(item => (
              <label className="setting-toggle" key={item.key}>
                <input type="checkbox" checked={Boolean(prefs[item.key])} onChange={event => commit({...prefs, [item.key]: event.target.checked})} />
                <span>{item.label}<small>{item.hint}</small></span>
              </label>
            ))}
          </div>
        </section>
      </div>
    </Modal>
  );
}

const PARAM_HELP: Record<string, string> = {
  trade_seconds: '阵亡后多久内被队友补掉，仍算“有贡献”。',
  window_start_ms: '击杀前观察窗口的起点。',
  window_end_ms: '击杀前观察窗口的终点，负数表示在击杀之前。',
  horizontal_cone_deg: '判断目标是否在准星前方水平范围的角度。',
  eye_stand: '站立时眼睛高度的模型参数。',
  eye_duck: '蹲伏时眼睛高度的模型参数。',
  head_stand: '站立时头部高度的模型参数。',
  head_duck: '蹲伏时头部高度的模型参数。',
  head_radius: '估计头部的半径。',
  flash_exclude_seconds: '致盲后多久内的采样不进入瞄准统计。',
  kill_min_coverage: '击杀窗口最少需要多少有效采样。',
  threshold_scale: '武器停步速度参考值的缩放倍率。',
  movement_lookback_ms: '开枪前回看多久的运动。',
  movement_min_ms: '至少持续多久的移动才算“移动后开枪”。',
  movement_enter_multiplier: '判定进入移动状态的滞回倍率。',
  boundary_margin: '接近速度阈值时的模糊带，避免硬切。',
  min_burst_shots: '连续射击片段至少需要几发。',
  pose_change_limit: '姿态变化超过多少就不按同一段处理。',
  before_death_seconds: '死亡复盘向前截取多久。',
  after_death_seconds: '死亡复盘向后截取多久。',
  engagement_gap_seconds: '两次交火间隔多久就切开。',
  speed_margin: '速度比较时保留的余量。',
  kill_window_seconds: '闪光后多久内发生的击杀才算关联。',
};

export function ParamsDialog({open, onClose, modules, selectedModules, onToggle, params, onParams, activeJob, onApply, result, steamIds, onSteamIds}: {
  open: boolean;
  onClose: () => void;
  modules: Obj[];
  selectedModules: string[];
  onToggle: (id: string, enabled: boolean) => void;
  params: Obj;
  onParams: (next: Obj) => void;
  activeJob: string;
  onApply: () => void;
  result: Obj | null;
  steamIds: string;
  onSteamIds: (value: string) => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title="分析配置" eyebrow="RUN CONFIGURATION" label="分析配置" size="lg"
      footer={<div className="params-foot"><span className="muted">阈值为实验参数；修改不会改变原始事实。</span><button type="button" onClick={onClose}>关闭</button><button type="button" className="primary" disabled={!activeJob || !selectedModules.length} onClick={onApply}>用当前配置重新分析</button></div>}>
      <p className="muted">选择要运行的模块并调整阈值。重新分析会创建新任务；可复用的解析结果与模块缓存仍会复用。</p>
      <Field label="指定 SteamID（玩家唯一编号，可选）" hint="留空分析全部玩家。多个 ID 用逗号分隔；一个个人存档可以绑定多个 ID。">
        <input value={steamIds} onChange={event => onSteamIds(event.target.value)} placeholder="例如 76561198041683378, 76561198074762801" />
      </Field>
      <div className="params-list">
        {modules.map(module => {
          const properties = module.parameters_schema_body?.properties || {};
          const isSelected = selectedModules.includes(module.id);
          return (
            <section className={'param-module' + (isSelected ? ' selected' : '')} key={module.id}>
              <header>
                <label className="param-check">
                  <input type="checkbox" disabled={!module.enabled} checked={isSelected} onChange={event => onToggle(module.id, event.target.checked)} />
                  <span><strong>{module.title}</strong><small>{module.enabled ? 'v' + module.version : '规划中，暂不可运行'}</small></span>
                </label>
                {module.enabled && Object.keys(properties).length > 0 && <button type="button" className="ghost" onClick={() => onParams({...params, [module.id]: module.defaults})}>恢复默认</button>}
              </header>
              {Object.keys(properties).length > 0 && (
                <div className="param-grid">
                  {Object.entries(properties as Record<string, any>).map(([key, schema]) => (
                    <label key={key}>
                      <span>{PARAM_NAMES[key] || schema.title || key}</span>
                      <input type="number" step={schema.type === 'integer' ? 1 : 'any'} min={schema.minimum} max={schema.maximum}
                        value={params[module.id]?.[key] ?? schema.default}
                        onChange={event => onParams({...params, [module.id]: {...params[module.id], [key]: Number(event.target.value)}})} />
                      <small>{PARAM_HELP[key] || '分析参数'}</small>
                    </label>
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
      {result && <p className="muted">当前结果的模块版本：{Object.entries(result.modules).map(([id, module]: [string, any]) => id + ' ' + (module.metrics?.[0]?.algorithm_version || '?')).join(' · ')}</p>}
    </Modal>
  );
}
