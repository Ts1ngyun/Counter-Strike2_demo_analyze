import React, {useEffect, useMemo, useRef, useState} from 'react';
import Icon from '../ui/Icon';
import {Badge, Callout, Coverage, EmptyState, Field, Segmented, Spinner} from '../ui/primitives';
import Explain from '../explain/MetricExplain';
import {metricCopy, metricName} from '../explain/dictionary';
import {api, ApiError} from '../app/api';
import {
  coverageText, evidenceKindText, evidenceReasonText, exclusionText, formatNumber, metricDisplay, phaseText, qualityText,
  statusText, teamName, unitLabel,
} from '../app/format';
import type {Job, Metric, Obj, Result, RoundStatRow, RoundStatsResponse} from '../app/format';
import type {Preferences} from '../theme/appearance';
import CombatReview from '../CombatReview';
import FlashReview from '../FlashReview';
import EvidenceDetail from './EvidenceDetail';
import MatchHighlights from './MatchHighlights';
import './analysis.css';

type ScopeMode = 'match' | 'round';
type OpenReplay = (focus: {tick: number; round_id?: string; player_id?: string}, jobId?: string) => void;

const MODULE_INTRO: Record<string, string> = {
  basic_stats: '查看全场表现，或切换到单回合。',
  combat_review: '按回合查看交战与死亡片段。',
  head_line: '查看交战前后的视角移动。',
  stop_shooting: '看移动后第一次开枪时速度是否已降下来。它只描述开枪瞬间的速度状态，不判断是否按了反向键。',
  recoil_control: '查看连射时的视角变化和射击片段。',
  utility_analysis: '逐颗闪光查看引爆、受影响的人与闪后击杀关联。记录不到效果不等于没有效果。',
};

const GROUP_ORDER = ['击杀与对抗', '进攻贡献', '开局', '生存与贡献', '伤害与细节', '击杀前窗口', '死亡前窗口', '未击杀交战', '实验几何（估计）', '停步口径', '连续射击', '闪光影响', '复盘片段', '其他指标'];

const JUDGEMENT_LABELS: Record<string, string> = {
  observed: '观测事实',
  derived: '计算得出',
  ready: '速度达标',
  moving: '高于参考',
  ambiguous: '阈值边界',
  unknown: '未知',
  excluded: '已排除',
  in_band: '头带内',
  high: '偏高',
  low: '偏低',
  descriptive: '描述性',
  review_candidate: '复盘候选',
};

function judgementTone(value: string): string {
  if (value === 'ready' || value === 'in_band') return 'ok';
  if (value === 'moving' || value === 'ambiguous' || value === 'high' || value === 'low') return 'warn';
  if (value === 'excluded') return 'danger';
  return 'neutral';
}

function groupFor(moduleId: string, metric: Metric): string {
  const id = metric.metric_id;
  if (moduleId === 'basic_stats') {
    if (['round_swing'].includes(id)) return '进攻贡献';
    if (['kills', 'deaths', 'assists', 'kd', 'kpr', 'dpr', 'hs_kills', 'hs_kill_pct', 'flash_assists'].includes(id)) return '击杀与对抗';
    if (id.startsWith('opening')) return '开局';
    if (['survival_rate', 'kast_local', 'participated_rounds'].includes(id)) return '生存与贡献';
    return '伤害与细节';
  }
  if (moduleId === 'head_line') {
    if (id.startsWith('kill_') || id === 'eligible_kill_windows') return '击杀前窗口';
    if (id.startsWith('death_') || id === 'death_windows') return '死亡前窗口';
    if (id.startsWith('nonkill_') || id === 'nonkill_windows') return '未击杀交战';
    return '实验几何（估计）';
  }
  if (moduleId === 'stop_shooting') return '停步口径';
  if (moduleId === 'recoil_control') return '连续射击';
  if (moduleId === 'utility_analysis') return '闪光影响';
  if (moduleId === 'combat_review') return '复盘片段';
  return '其他指标';
}

function displayFor(metric: Metric, roundMode: boolean) {
  if (roundMode && metric.metric_id === 'kast_local') {
    if (metric.value === 1) return {text: '是', suffix: '', unavailable: null};
    if (metric.value === 0) return {text: '否', suffix: '', unavailable: null};
  }
  if (roundMode && metric.metric_id === 'survival_rate') {
    if (metric.value === 1) return {text: '存活', suffix: '', unavailable: null};
    if (metric.value === 0) return {text: '阵亡', suffix: '', unavailable: null};
  }
  return metricDisplay(metric);
}

function MetricCard({metric, definition, moduleId, roundMode, prefs, onEvidence}: {
  metric: Metric;
  definition: Obj;
  moduleId: string;
  roundMode: boolean;
  prefs: Preferences;
  onEvidence: () => void;
}) {
  const display = displayFor(metric, roundMode);
  const copy = metricCopy(metric.metric_id, definition);
  const unavailable = metric.value === null;
  const showQuality = prefs.qualityLabels || ['estimated', 'unknown'].includes(metric.quality);
  return (
    <article className={'stat-card' + (unavailable ? ' unavailable' : '') + (metric.quality === 'estimated' ? ' estimated' : '')}>
      <div className="stat-card-head">
        <span className="stat-title">{metricName(metric.metric_id, definition)}<Explain metricId={metric.metric_id} definition={definition} metric={metric} /></span>
        {showQuality && <span className={'quality-tag ' + metric.quality}>{qualityText(metric.quality)}</span>}
      </div>
      <div className="stat-value">
        <strong>{display.text}</strong>{display.suffix && <em>{display.suffix}</em>}
      </div>
      {(unavailable || !['kd', 'kpr', 'dpr', 'kast_local'].includes(metric.metric_id)) && <p className={'stat-line' + (unavailable ? ' unavailable-line' : '')}>{unavailable ? display.unavailable : copy.oneLine}</p>}
      <Coverage value={metric.coverage} showFull={prefs.fullCoverage} bar />
      {metric.coverage === 0 && metric.value !== null && <span className="coverage-note">这项是估计值：暂无样本能完全核实，数值不应当作确切结果。</span>}
      {metric.eligible_count > 0 && metric.eligible_count < 20 && <span className="small-sample">有效样本较少（{formatNumber(metric.eligible_count, 0)}）</span>}
      {prefs.sampleDetails && (
        <span className="sample-details">
          {metric.denominator !== null && metric.denominator !== undefined
            ? '分子 / 分母 ' + formatNumber(metric.numerator) + ' / ' + formatNumber(metric.denominator)
            : '有效样本 ' + formatNumber(metric.evaluated_count, 0)}
          {' · 未知 ' + formatNumber(metric.unknown_count, 0) + ' · 排除 ' + formatNumber(metric.excluded_count, 0)}
        </span>
      )}
      <button type="button" className="stat-evidence" onClick={onEvidence}>查看明细 <Icon name="arrow-right" size={13} /></button>
    </article>
  );
}

function Distribution({title, rows, unit, note}: {title: string; rows: {label: string; value: number}[]; unit?: string; note?: string}) {
  const max = Math.max(...rows.map(row => row.value), 0.001);
  return (
    <section className="panel distribution-panel">
      <div className="section-head"><div><h3>{title}</h3>{note && <p>{note}</p>}</div></div>
      <div className="distribution">
        {rows.map(row => (
          <div key={row.label}>
            <span>{row.label}</span>
            <i style={{width: Math.max(1, row.value / max * 100) + '%'}} />
            <small>{formatNumber(row.value, 2)} {unitLabel(unit)}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Analysis({
  result, job, active, modules, manifest, moduleId, onModule,
  player, onPlayer, round, onRound, scopeMode, onScope, prefs,
  onOpenConfig, onReplay, onRerun,
}: {
  result: Result;
  job?: Job;
  active: string;
  modules: Obj[];
  manifest?: Obj;
  moduleId: string;
  onModule: (id: string) => void;
  player: string;
  onPlayer: (id: string) => void;
  round: string;
  onRound: (id: string) => void;
  scopeMode: ScopeMode;
  onScope: (mode: ScopeMode) => void;
  prefs: Preferences;
  onOpenConfig: () => void;
  onReplay: OpenReplay;
  onRerun: () => void;
}) {
  const module = result.modules[moduleId];
  const [layout, setLayout] = useState<'cards'|'list'>(() => {try {return localStorage.getItem('demo-lab.metric-layout') === 'list' ? 'list' : 'cards';} catch {return 'cards';}});
  useEffect(() => {try {localStorage.setItem('demo-lab.metric-layout',layout);} catch {}},[layout]);
  const [viewOptions, setViewOptions] = useState<Obj>({});
  const [weapon, setWeapon] = useState('');
  const [team, setTeam] = useState('');
  const [pose, setPose] = useState('');
  const [distance, setDistance] = useState('');
  const [judge, setJudge] = useState('');
  const [advanced, setAdvanced] = useState(false);
  const [metricFilter, setMetricFilter] = useState('');
  const [page, setPage] = useState(0);
  const [evidence, setEvidence] = useState<Obj[]>([]);
  const [evidenceTotal, setEvidenceTotal] = useState(0);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState('');
  const [detail, setDetail] = useState<Obj | null>(null);
  const [roundStats, setRoundStats] = useState<RoundStatsResponse | null>(null);
  const [roundState, setRoundState] = useState<'idle' | 'loading' | 'ready' | 'empty' | 'stale' | 'error'>('idle');
  const [roundError, setRoundError] = useState('');
  const [roundNonce, setRoundNonce] = useState(0);
  const evidenceBox = useRef<HTMLElement | null>(null);

  const presentation = manifest?.presentation || {};
  const option = (field: string, fallback: string) => viewOptions[moduleId]?.[field] ?? fallback;
  const scopeOptions: Obj = Object.fromEntries((presentation.scope_selectors || []).map((item: Obj) => [item.field, option(item.field, item.default)]));
  const evidenceOptions: Obj = Object.fromEntries((presentation.evidence_selectors || []).map((item: Obj) => [item.field, option(item.field, item.default)]));
  const selectedMetric = presentation.metric_selector ? option('metric', presentation.metric_selector.default) : '';
  const selectionKey = JSON.stringify([scopeOptions, evidenceOptions, selectedMetric]);

  useEffect(() => {
    setWeapon(''); setTeam(''); setPose(''); setDistance(''); setJudge('');
    setAdvanced(false); setPage(0); setMetricFilter(''); setDetail(null); setEvidence([]);
    setEvidenceTotal(0); setEvidenceError(''); setViewOptions({});
  }, [active, moduleId]);

  useEffect(() => {
    setPage(0); setMetricFilter(''); setDetail(null);
  }, [player, round, weapon, pose, judge, team, distance, selectionKey]);

  useEffect(() => {
    if (scopeMode !== 'round') return;
    setAdvanced(false); setTeam(''); setPose(''); setDistance(''); setWeapon('');
  }, [scopeMode]);

  const definition = (id: string): Obj => module?.metrics?.find((metric: Metric) => metric.metric_id === id)?.definition || manifest?.metric_definitions?.[id] || {};
  const label = (id: string) => metricName(id, definition(id));

  const metrics = useMemo<Metric[]>(() => {
    if (!module?.metrics) return [];
    return module.metrics
      .filter((metric: Metric) => metric.metric_id !== 'impact')
      .filter((metric: Metric) => !player || metric.scope.player_id === player)
      .filter((metric: Metric) => team ? String(metric.scope.team) === team : !metric.scope.team)
      .filter((metric: Metric) => weapon ? metric.scope.weapon === weapon : !metric.scope.weapon)
      .filter((metric: Metric) => pose ? metric.scope.self_pose === pose : !metric.scope.self_pose)
      .filter((metric: Metric) => metric.scope.grounded === undefined)
      .filter((metric: Metric) => distance ? metric.scope.distance_bucket === distance : !metric.scope.distance_bucket)
      .filter((metric: Metric) => !selectedMetric || metric.metric_id === selectedMetric)
      .filter((metric: Metric) => Object.entries(scopeOptions).every(([key, value]) => metric.scope[key] === value || metric.scope[key] === undefined));
  }, [module, player, team, weapon, pose, distance, selectedMetric, scopeOptions]);

  const availableWeapons = useMemo(() => {
    if (!module?.metrics) return [] as string[];
    return Array.from(new Set<string>(module.metrics
      .filter((metric: Metric) => Object.entries(scopeOptions).every(([key, value]) => metric.scope[key] === value || metric.scope[key] === undefined))
      .map((metric: Metric) => metric.scope.weapon)
      .filter(Boolean)));
  }, [module, scopeOptions]);

  const metricIds = Array.from(new Set(metrics.map(metric => metric.metric_id)));
  const players = result.players || [];
  const playerName = (id: string) => players.find(item => item.player_id === id)?.name || id;
  const reviewModule = ['combat_review', 'utility_analysis'].includes(moduleId);
  const supportsRound = moduleId === 'basic_stats';
  const roundInfo = result.rounds.find(item => item.round_id === round);
  const moduleVersion = module?.metrics?.[0]?.identities?.module_version;
  const staleModule = Boolean(moduleVersion && manifest?.version && moduleVersion !== manifest.version);

  useEffect(() => {
    setRoundStats(null);
    setRoundState('idle');
    setRoundError('');
    if (scopeMode !== 'round' || !supportsRound || !round) return;
    const controller = new AbortController();
    setRoundState('loading');
    api('/jobs/' + active + '/round-stats?round_id=' + encodeURIComponent(round), {signal: controller.signal})
      .then(data => {
        if (!data.total) { setRoundState('empty'); return; }
        setRoundStats(data);
        setRoundState('ready');
      })
      .catch(error => {
        if (error?.name === 'AbortError') return;
        if (error instanceof ApiError && error.status === 409) { setRoundState('stale'); return; }
        setRoundState('error');
        setRoundError(error?.message || String(error));
      });
    return () => controller.abort();
  }, [scopeMode, supportsRound, active, round, roundNonce]);

  useEffect(() => {
    if (!module || !result) return;
    if (reviewModule) return;
    const controller = new AbortController();
    const query = new URLSearchParams({offset: String(page * 30), limit: '30'});
    Object.entries({player, round_id: round, weapon, judgement: judge, pose, team, distance, metric_id: metricFilter || selectedMetric, ...scopeOptions, ...evidenceOptions})
      .forEach(([key, value]) => { if (value) query.set(key, String(value)); });
    setEvidenceLoading(true);
    setEvidenceError('');
    api('/jobs/' + active + '/evidence/' + moduleId + '?' + query.toString(), {signal: controller.signal})
      .then(data => { setEvidence(data.rows); setEvidenceTotal(data.total); })
      .catch(error => { if (error?.name !== 'AbortError') setEvidenceError(error?.message || String(error)); })
      .finally(() => { if (!controller.signal.aborted) setEvidenceLoading(false); });
    return () => controller.abort();
  }, [active, module, moduleId, player, round, weapon, pose, judge, team, distance, page, metricFilter, selectedMetric, selectionKey, reviewModule]);

  const updateOption = (field: string, value: string) => {
    setViewOptions({...viewOptions, [moduleId]: {...viewOptions[moduleId], [field]: value}});
    setPage(0); setMetricFilter(''); setDetail(null);
  };

  const clearFilters = () => {
    onPlayer(''); onRound(''); setWeapon(''); setTeam(''); setPose(''); setDistance(''); setJudge('');
    setAdvanced(false); setMetricFilter(''); setPage(0);
  };
  const activeFilterCount = [player, round, weapon, team, pose, distance, judge, metricFilter].filter(Boolean).length;

  const scrollToEvidence = () => { evidenceBox.current?.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'}); };

  if (!manifest) {
    return <EmptyState icon="warning" title="找不到这个模块">页面拿到的是未知模块 ID，可能是前端与后端版本不一致。请刷新或重新打开任务。</EmptyState>;
  }

  if (!manifest.enabled) {
    return (
      <EmptyState icon="clock" title="这个模块还在规划中" actions={<><button type="button" onClick={onOpenConfig}>查看分析配置</button><button type="button" onClick={() => onModule('basic_stats')}>回到基础统计</button></>}>
        <p>该能力尚未实现，不会运行，也不会产生评分或结论。规划中的模块不会出现在主要结果里。</p>
      </EmptyState>
    );
  }

  if (!module) {
    return (
      <EmptyState icon="pulse" title="本次任务没有启用这个模块" actions={<button type="button" className="primary" onClick={onOpenConfig}>打开分析配置</button>}>
        <p>在分析配置中勾选「{manifest.title}」，然后用当前参数重新分析。旧任务不会自动补算。</p>
      </EmptyState>
    );
  }

  const heroId = moduleId === 'basic_stats' ? '' : moduleId === 'head_line' ? 'kill_pitch_span_p50' : moduleId === 'stop_shooting' ? (selectedMetric || 'movement_to_first_shot_ready_rate') : moduleId === 'recoil_control' ? 'view_pitch_delta_p50' : moduleId === 'utility_analysis' ? 'enemy_affected_flashes' : '';
  const heroMetric = player ? metrics.find(metric => metric.metric_id === heroId) || null : null;

  const grouped = new Map<string, Metric[]>();
  for (const metric of metrics) {
    if (heroMetric && metric === heroMetric) continue;
    const group = groupFor(moduleId, metric);
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group)!.push(metric);
  }
  const groupOrder = GROUP_ORDER.filter(name => grouped.has(name));

  const roundRow: RoundStatRow | null = roundStats?.rows.find(row => row.player_id === player) || null;
  const roundMetrics = (roundRow?.metrics || []).filter(metric => metric.metric_id !== 'impact').filter(metric => !selectedMetric || metric.metric_id === selectedMetric);
  const sortedRoundRows = [...(roundStats?.rows || [])].sort((a, b) => (a.team || 0) - (b.team || 0) || playerName(a.player_id).localeCompare(playerName(b.player_id), 'zh-CN'));

  const multiKill = module.details?.multi_kill_round_distribution;
  const experimental = module.details?.experimental_geometry?.distributions || [];
  const generic = module.details?.distributions || [];

  const filterSummary = [
    player && '玩家 ' + playerName(player),
    round && '回合 ' + round,
    weapon && '武器 ' + weapon,
    team && '阵营 ' + team,
    pose && '姿态 ' + pose,
    distance && '距离 ' + distance,
    judge && '判定 ' + (JUDGEMENT_LABELS[judge] || judge),
    metricFilter && '指标 ' + label(metricFilter),
  ].filter(Boolean) as string[];

  return (
    <div className="analysis" data-layout={layout}>
      <div className="module-rail" role="tablist" aria-label="分析模块">
        {modules.filter(item => item.enabled).map(item => {
          const status = result.modules[item.id]?.status;
          return (
            <button key={item.id} type="button" role="tab" aria-selected={moduleId === item.id}
              className={'module-chip' + (moduleId === item.id ? ' active' : '')}
              onClick={() => onModule(item.id)}>
              <span>{item.title}</span>
              {status && <i className={'module-dot ' + status} aria-hidden="true" />}
            </button>
          );
        })}
      </div>

      <header className="module-header">
        <div className="module-heading">
          <span className="eyebrow">{statusText(module.status)}{prefs.technicalDetails ? ' · v' + (moduleVersion || manifest.version) : ''}{module.status === 'partial' && <Explain term="partial" compact />}</span>
          <h2>{manifest.title}</h2>
          <p>{MODULE_INTRO[moduleId] || '本模块的真实分析结果与证据。'}</p>
        </div>
        <div className="module-heading-actions">
          <Segmented label="指标布局" value={layout} onChange={v=>setLayout(v as 'cards'|'list')} options={[{value:'cards',label:'方块'},{value:'list',label:'列表'}]}/>
          <Segmented
            label="统计范围"
            value={scopeMode}
            onChange={value => onScope(value as ScopeMode)}
            options={[
              {value: 'match', label: '全场'},
              {value: 'round', label: '单回合', disabled: !supportsRound && !reviewModule, hint: supportsRound ? '只改变基础统计口径' : reviewModule ? '只筛选复盘片段' : '该模块暂无单回合聚合'},
            ]}
          />
          <button type="button" className="ghost" onClick={onOpenConfig}><Icon name="sliders" size={15} />分析配置</button>
        </div>
      </header>

      {module.error && <Callout tone="danger" title="模块执行失败">{module.error}</Callout>}
      {staleModule && (
        <Callout tone="warn" title="这是旧版本模块的结果" action={<button type="button" onClick={onRerun}>用当前版本重算</button>}>
          当前模块版本为 {manifest.version}，结果来自 {moduleVersion}。新增筛选或新增字段可能不可用；重算会尽量复用已缓存事实。
        </Callout>
      )}

      <section className="filter-bar" aria-label="筛选与统计口径">
        <div className="filter-fields">
          <Field label="玩家">
            <select value={player} onChange={event => onPlayer(event.target.value)}>
              <option value="">全部玩家</option>
              {players.map(item => <option key={item.player_id} value={item.player_id}>{item.name}</option>)}
            </select>
          </Field>
          <Field label={scopeMode === 'round' ? '回合（单回合统计）' : '回合（仅筛证据）'}>
            <select value={round} onChange={event => onRound(event.target.value)}>
              <option value="">全部回合</option>
              {result.rounds.map(item => <option key={item.round_id} value={item.round_id}>{item.round_id + ' · ' + phaseText(item.phase) + (item.complete ? '' : ' · 未计入')}</option>)}
            </select>
          </Field>
          {!reviewModule && (
            <Field label="武器">
              <select value={weapon} disabled={scopeMode === 'round'} onChange={event => setWeapon(event.target.value)}>
                <option value="">全部武器</option>
                {availableWeapons.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
            </Field>
          )}
          {!reviewModule && (
            <button type="button" className="filter-toggle" aria-expanded={advanced || Boolean(team || pose || distance || judge)} onClick={() => {
              if (advanced || team || pose || distance || judge) { setAdvanced(false); setTeam(''); setPose(''); setDistance(''); setJudge(''); }
              else setAdvanced(true);
            }}>{advanced || team || pose || distance || judge ? '收起更多筛选' : '更多筛选'}</button>
          )}
          <button type="button" className="ghost clear-filters" disabled={!activeFilterCount} onClick={clearFilters}>清除筛选{activeFilterCount ? '（' + activeFilterCount + '）' : ''}</button>
          <span className="filter-spacer" />
          <span className="filter-result-count">{metrics.length} 项指标</span>
        </div>

        {scopeMode === 'match' && (advanced || team || pose || distance || judge) && !reviewModule && (
          <div className="advanced-filters">
            <Field label="阵营"><select value={team} onChange={event => setTeam(event.target.value)}><option value="">全部阵营</option><option value="2">T</option><option value="3">CT</option></select></Field>
            <Field label="自己姿态"><select value={pose} onChange={event => setPose(event.target.value)}><option value="">全部姿态</option>{['站立', '蹲伏', '过渡'].map(item => <option key={item}>{item}</option>)}</select></Field>
            <Field label="距离">
              <select value={distance} onChange={event => setDistance(event.target.value)}>
                <option value="">全部距离</option>
                {['<250', '250–500', '500–1000', '1000–2000', '≥2000'].map(item => <option key={item}>{item}</option>)}
              </select>
            </Field>
            <Field label="证据判定">
              <select value={judge} onChange={event => setJudge(event.target.value)}>
                <option value="">全部判定</option>
                {['ready', 'moving', 'ambiguous', 'unknown', 'excluded', 'in_band', 'high', 'low', 'descriptive'].map(item => <option key={item} value={item}>{JUDGEMENT_LABELS[item] || item}</option>)}
              </select>
            </Field>
          </div>
        )}

        <div className="analysis-controls">
          {presentation.metric_selector && (
            <Field label={presentation.metric_selector.label}>
              <select value={selectedMetric} onChange={event => updateOption('metric', event.target.value)}>
                {presentation.metric_selector.options.map((item: Obj) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </Field>
          )}
          {[...(presentation.scope_selectors || []), ...(presentation.evidence_selectors || [])].map((control: Obj) => (
            <Field key={control.field} label={control.label}>
              <select value={option(control.field, control.default)} onChange={event => { updateOption(control.field, event.target.value); setWeapon(''); }}>
                {control.options.map((item: Obj) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </Field>
          ))}
          {selectedMetric && (
            <div className="active-metric">
              <span className="field-label">当前口径</span>
              <strong>{label(selectedMetric)} <Explain metricId={selectedMetric} definition={definition(selectedMetric)} /></strong>
            </div>
          )}
        </div>
        {filterSummary.length > 0 && (
          <div className="active-filters" aria-label="当前筛选">
            {filterSummary.map(text => <span className="filter-chip" key={text}>{text}</span>)}
          </div>
        )}
      </section>

      {scopeMode === 'round' && supportsRound && (
        <section className="round-workspace">
          <div className="round-picker" aria-label="选择回合">
            {result.rounds.map(item => (
              <button type="button" key={item.round_id} className={'round-pick' + (round === item.round_id ? ' active' : '') + (item.complete ? '' : ' excluded')} onClick={() => onRound(item.round_id)} aria-pressed={round === item.round_id}>
                <strong>{item.round_id}</strong><span>{item.winner ? item.winner + ' 胜' : phaseText(item.phase)}</span>
              </button>
            ))}
          </div>

          {!round && (
            <EmptyState icon="target" title="先选一个回合" actions={<button type="button" onClick={() => onRound(result.rounds[0]?.round_id || '')}>从第一回合开始</button>}>
              <p>单回合视图只使用「基础比赛统计」的 round-stats 接口。其他模块仍以全场统计呈现。</p>
            </EmptyState>
          )}

          {round && roundInfo && !roundInfo.complete && (
            <Callout tone="warn" title="这个回合未计入比赛统计">{exclusionText(roundInfo.exclusion_reason || roundInfo.reason)} 你仍然可以查看事件与证据，但它不会进入全场分母。</Callout>
          )}

          {round && roundState === 'loading' && <div className="round-loading"><Spinner label="正在读取这一回合的基础统计…" /></div>}
          {round && roundState === 'stale' && (
            <Callout tone="warn" title="这份结果没有单回合统计" action={<><button type="button" className="primary" onClick={onRerun}>按当前版本重新分析</button><button type="button" onClick={onOpenConfig}>检查模块设置</button></>}>
              单回合数据来自基础比赛统计模块 v1.1.0。旧结果或未启用该模块的任务会返回 409。重新分析会复用已缓存的事实；没有新字段的旧结果不会被猜测补齐。
            </Callout>
          )}
          {round && roundState === 'error' && (
            <Callout tone="danger" title="读取单回合统计失败" action={<button type="button" onClick={() => setRoundNonce(value => value + 1)}>重试</button>}>
              {roundError} <span className="muted">如果问题持续，请确认任务仍在本地、结果未被清理。</span>
            </Callout>
          )}
          {round && roundState === 'empty' && (
            <Callout tone="info" title="这一回合没有可用的基础统计">
              可能是未计入回合、比分未知，或该回合没有足够的事件。空结果不会用 0 填充。
            </Callout>
          )}

          {round && roundState === 'ready' && roundInfo && (
            <>
              <div className="round-summary">
                <div>
                  <span className="eyebrow">单回合 · {phaseText(roundInfo.phase)}</span>
                  <h2>{roundInfo.round_id} {roundInfo.winner ? '· ' + roundInfo.winner + ' 方获胜' : ''}</h2>
                  <p>录像累计总比分 {formatNumber(roundInfo.score_after_total, 0)}（双方合计） · 本回合比分变化 {roundInfo.score_delta === null || roundInfo.score_delta === undefined ? '未知' : formatNumber(roundInfo.score_delta, 0)}。单回合统计不参与全场比例的平均。</p>
                </div>
                <span className={'pill ' + (roundInfo.complete ? 'ok' : 'warn')}>{roundInfo.complete ? '计入比赛统计' : '未计入'}</span>
              </div>

              <section className="panel round-table-panel">
                <div className="section-head"><div><h2>这一回合的球员数据</h2><p>点击玩家查看该回合的指标卡片；所有数值来自 round-stats 接口。</p></div></div>
                <div className="table-scroll" tabIndex={0} role="region" aria-label="单回合球员数据表，可横向滚动">
                  <table className="round-table">
                    <thead>
                      <tr>
                        <th>玩家</th><th>阵营</th><th>击杀</th><th>死亡</th><th>助攻</th><th>K/D</th><th>KAST <Explain metricId="kast_local" /></th><th>本回合伤害 <Explain metricId="adr_raw" /></th><th>有效伤害 <Explain metricId="adr_effective" /></th><th>爆头击杀</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedRoundRows.map(row => {
                        const find = (id: string) => row.metrics.find(metric => metric.metric_id === id);
                        const cell = (id: string) => {
                          const metric = find(id);
                          if (!metric) return '—';
                          const display = displayFor(metric, true);
                          return display.text + (display.suffix ? ' ' + display.suffix : '');
                        };
                        const effective = find('adr_effective');
                        return (
                          <tr key={row.player_id} className={row.player_id === player ? 'selected-row clickable' : 'clickable'} tabIndex={0} onClick={() => onPlayer(row.player_id)} onKeyDown={event => { if (event.key === 'Enter') onPlayer(row.player_id); }} aria-label={'查看 ' + playerName(row.player_id) + ' 本回合数据'}>
                            <td><span className="round-player">{playerName(row.player_id)}</span></td>
                            <td><span className={'side-tag side-' + row.team}>{row.team === 2 ? 'T' : row.team === 3 ? 'CT' : teamName(row.team)}</span></td>
                            <td className="num">{cell('kills')}</td>
                            <td className="num">{cell('deaths')}</td>
                            <td className="num">{cell('assists')}</td>
                            <td className="num">{cell('kd')}</td>
                            <td className="num">{cell('kast_local')}</td>
                            <td className="num">{cell('adr_raw')}</td>
                            <td className="num">{effective && effective.value === null ? <span className="cell-unknown">暂不可用</span> : cell('adr_effective')}</td>
                            <td className="num">{cell('hs_kills')}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <p className="muted round-note">单回合表格里的 KAST 用「是 / 否」表示是否满足条件，不是百分比；存活状态在个人卡片里显示为「存活 / 阵亡」。本回合伤害就是这一回合记录的伤害，不要把单回合的 0 / 1 平均成全场比例。</p>
              </section>

              {player && roundRow && (
                <section className="round-player-section">
                  <div className="section-head"><div><h2>{playerName(player)} · 这一回合</h2><p>只解释本回合的值；全场统计请切回「全场」。</p></div><button type="button" className="ghost" onClick={() => onScope('match')}>查看全场</button></div>
                  <div className="metric-grid compact-grid">
                    {roundMetrics
                      .filter(metric => ['kills', 'deaths', 'assists', 'kd', 'kast_local', 'survival_rate', 'adr_raw', 'adr_effective', 'hs_kills', 'opening_kills', 'opening_deaths', 'flash_assists'].includes(metric.metric_id))
                      .map(metric => (
                        <MetricCard key={metric.metric_id} metric={metric} definition={definition(metric.metric_id)} moduleId={moduleId} roundMode prefs={prefs}
                          onEvidence={() => { setMetricFilter(metric.metric_id); setPage(0); scrollToEvidence(); }} />
                      ))}
                  </div>
                </section>
              )}

              {!player && <Callout tone="info" title="选一名玩家看解释">点击表格里的任意一行，可以查看这名玩家本回合的卡片、通俗解释与证据。</Callout>}
            </>
          )}
        </section>
      )}

      {scopeMode === 'match' && reviewModule && !player && (
        <Callout tone="info" title="选一名玩家查看个人片段">
          当前列表会展示所有玩家；选择玩家后，指标卡片和复盘片段都会只针对这名玩家。玩家名称与字符串 ID 的关联仍按真实 SteamID 展示。
        </Callout>
      )}

      {scopeMode === 'round' && !supportsRound && (
        <Callout tone="warn" title={reviewModule ? '回合筛选只作用于复盘片段' : '这个模块目前只有全场统计'}>
          {reviewModule
            ? '片段列表会按所选回合过滤；顶部的片段计数与指标仍是全场口径，不会伪装成本回合。'
            : '这个模块还没有单回合聚合，切到「单回合」不会改变它的数值。为避免误读，这里不把全场值展示成回合值；请切回「全场」查看。'}
          <div className="callout-actions"><button type="button" onClick={() => onScope('match')}>回到全场</button>{reviewModule && <button type="button" onClick={onOpenConfig}>调整参数</button>}</div>
        </Callout>
      )}

      {scopeMode === 'match' && !reviewModule && (
        <>
          {!player && (
            <section className="panel roster-panel">
              <div className="section-head"><div><h2>先选一名玩家</h2><p>点击玩家名字查看个人指标；点击指标值会直接筛出对应证据。</p></div><span className="muted">全部玩家 · {metricIds.length} 项指标</span></div>
              <p className="roster-scroll-hint">左右滑动表格，查看所有指标。</p>
              <div className="table-scroll roster-scroll" tabIndex={0} role="region" aria-label="玩家指标表，可横向滚动">
                <table className="roster-table">
                  <thead>
                    <tr>
                      <th className="sticky-player">玩家</th>
                      {metricIds.map(id => <th key={id}>{label(id)} <Explain metricId={id} definition={definition(id)} /></th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {players.map(item => (
                      <tr key={item.player_id}>
                        <td className="sticky-player">
                          <button type="button" className="player-name" onClick={() => onPlayer(item.player_id)}>{item.name}</button>
                          {prefs.technicalDetails && <small>{item.player_id}</small>}
                        </td>
                        {metricIds.map(id => {
                          const metric = metrics.find(candidate => candidate.metric_id === id && candidate.scope.player_id === item.player_id);
                          if (!metric) return <td key={id} className="num muted">—</td>;
                          const display = metricDisplay(metric);
                          return (
                            <td key={id} className="num">
                              <button type="button" className="table-value" onClick={() => { onPlayer(item.player_id); setMetricFilter(id); setPage(0); }}>{display.text}<span className="cell-suffix">{display.suffix}</span></button>
                              {metric.value === null && <small className="cell-unknown">不可用</small>}
                              <Coverage value={metric.coverage} showFull={prefs.fullCoverage} />
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {player && (
            <>
              {moduleId === 'basic_stats' && <section className="performance-strip" aria-label="表现摘要">
                {['kpr','kast_local','hs_kill_pct'].map(id => { const m=metrics.find(x=>x.metric_id===id); const d=m ? metricDisplay(m) : null; return <article key={id}><span>{label(id)} <Explain metricId={id} metric={m} /></span><strong>{d?.text ?? '—'}<small>{d?.suffix}</small></strong></article>; })}
                {['round_swing'].map(id=>{const m=metrics.find(x=>x.metric_id===id);const d=metricDisplay(m);return <article key={id} className="estimated-stat"><span>{metricName(id)} <Explain metricId={id} metric={m} definition={definition(id)}/></span><strong>{d.text}<small>{d.suffix}</small></strong><small>{m ? '实验 · 仅下包前' : '重算后可用'}</small>{m && <Coverage value={m.coverage} showFull={prefs.fullCoverage}/>}</article>;})}
              </section>}
              {moduleId === 'basic_stats' && <MatchHighlights result={result} player={player} onPlayer={onPlayer} team={team} onReplay={onReplay} onRerun={onRerun} />}
              {heroMetric && (
                <section className="hero-stat">
                  <div className="hero-stat-copy">
                    <span className="eyebrow">本场核心</span>
                    <h2>{metricName(heroMetric.metric_id, definition(heroMetric.metric_id))} <Explain metricId={heroMetric.metric_id} definition={definition(heroMetric.metric_id)} metric={heroMetric} /></h2>
                    <p>{metricCopy(heroMetric.metric_id, definition(heroMetric.metric_id)).oneLine}</p>
                    <div className="hero-stat-actions">
                      <button type="button" onClick={() => { setMetricFilter(heroMetric.metric_id); setPage(0); scrollToEvidence(); }}>看这项的证据</button>
                      <button type="button" className="ghost" onClick={() => {
                        const target = result.rounds.find(item => item.round_id === round) || result.rounds[0];
                        onReplay({tick: target?.live_tick ?? target?.start_tick ?? 0, round_id: target?.round_id, player_id: player});
                      }} disabled={!result.rounds.length}>在回放中看这场</button>
                    </div>
                  </div>
                  <div className="hero-stat-value">
                    {(() => { const display = metricDisplay(heroMetric); return <><strong>{display.text}</strong><em>{display.suffix}</em>{heroMetric.value === null && <small>{display.unavailable}</small>}</>; })()}
                    <span className="hero-stat-meta">{qualityText(heroMetric.quality)}{prefs.fullCoverage || heroMetric.coverage !== 1 ? ' · ' + coverageText(heroMetric.coverage) : ''}</span>
                  </div>
                </section>
              )}

              {groupOrder.map(group => (
                <section className="metric-group" key={group}>
                  <div className="section-head"><div><h3>{group}</h3><p>{group === '伤害与细节' ? '伤害口径与原始事件的分母不同，不要混着比较。' : group === '实验几何（估计）' ? '这些是几何估计，不是命中率。' : ''}</p></div></div>
                  <div className="metric-grid">
                    {grouped.get(group)!.map(metric => (
                      <MetricCard key={metric.metric_id + JSON.stringify(metric.scope)} metric={metric} definition={definition(metric.metric_id)} moduleId={moduleId} roundMode={false} prefs={prefs}
                        onEvidence={() => { setMetricFilter(metric.metric_id); setPage(0); scrollToEvidence(); }} />
                    ))}
                  </div>
                </section>
              ))}
            </>
          )}
        </>
      )}

      {scopeMode === 'match' && reviewModule && player && (
        <div className="metric-grid review-metrics">
          {metrics.map(metric => (
            <MetricCard key={metric.metric_id + JSON.stringify(metric.scope)} metric={metric} definition={definition(metric.metric_id)} moduleId={moduleId} roundMode={false} prefs={prefs}
              onEvidence={() => { setMetricFilter(metric.metric_id); setPage(0); }} />
          ))}
        </div>
      )}

      {moduleId === 'combat_review' && (
        <CombatReview jobId={active} playerId={player} roundId={round} players={result.players.map((person: Obj) => ({player_id: String(person.player_id), name: person.name}))} onReplay={focus => onReplay(focus)} technical={prefs.technicalDetails} />
      )}
      {moduleId === 'utility_analysis' && (
        <FlashReview module={module} result={result} player={player} roundId={round} onReplay={focus => onReplay(focus)} />
      )}

      {prefs.methodNotes && module.details?.notes?.length > 0 && (
        <section className="method-note">
          <strong>方法与边界</strong>
          {module.details.notes.map((note: string) => <p key={note}>{note}</p>)}
        </section>
      )}

      {moduleId === 'basic_stats' && ((scopeMode==='round' && round) || (scopeMode==='match' && !player)) && <MatchHighlights result={result} player={player} onPlayer={onPlayer} roundId={scopeMode==='round'?round:undefined} team={team} onReplay={onReplay} onRerun={onRerun} />}

      {scopeMode === 'match' && player && multiKill?.[player] && !module.details?.highlights && (
        <Distribution title={playerName(player) + ' · 每个回合的击杀数分布'} unit="回合" note="只看计数，不评价多杀质量；0 杀回合也会显示。"
          rows={Object.entries(multiKill[player]).sort(([a], [b]) => Number(a) - Number(b)).map(([kills, count]) => ({label: kills + ' 杀', value: Number(count)}))} />
      )}
      {scopeMode === 'match' && experimental
        .filter((distribution: Obj) => !player || distribution.player_id === player)
        .slice(0, player ? 4 : 2)
        .map((distribution: Obj, index: number) => (
          <Distribution key={index} title={playerName(distribution.player_id) + ' · ' + distribution.title} unit={distribution.unit}
            rows={distribution.bins.map((bin: Obj) => ({label: bin.label, value: bin.value}))} note="这是实验几何估计的时间分布，不是命中率。" />
        ))}
      {scopeMode === 'match' && generic
        .filter((distribution: Obj) => !player || distribution.player_id === player)
        .slice(0, player ? 6 : 2)
        .map((distribution: Obj, index: number) => (
          <Distribution key={'generic' + index} title={playerName(distribution.player_id) + ' · ' + distribution.title} unit={distribution.unit}
            rows={distribution.bins.map((bin: Obj) => ({label: bin.label, value: bin.value}))} />
        ))}

      {!reviewModule && (
        <section className="panel evidence-panel" ref={evidenceBox}>
          <div className="section-head">
            <div>
              <h2>事件明细 <span className="count-badge">{formatNumber(evidenceTotal, 0)} 条</span></h2>
              <p>点击记录查看详情。这里的筛选仅影响明细，不改变上方统计。</p>
            </div>
            <div className="evidence-pager">
              <button type="button" disabled={!page || evidenceLoading} onClick={() => setPage(value => Math.max(0, value - 1))}>上一页</button>
              <span>{page + 1} / {Math.max(1, Math.ceil(evidenceTotal / 30))}</span>
              <button type="button" disabled={(page + 1) * 30 >= evidenceTotal || evidenceLoading} onClick={() => setPage(value => value + 1)}>下一页</button>
            </div>
          </div>
          {metricFilter && <div className="evidence-filter-note">只显示「{label(metricFilter)}」的证据 <button type="button" className="ghost" onClick={() => setMetricFilter('')}>清除指标筛选</button></div>}
          <div className="evidence-hint">
            {round ? '回合筛选已开启：上方汇总指标仍使用其声明的完整分母。' : '当前显示全部回合的记录。'}
            {evidenceOptions.attack_input_status && ' 攻击输入筛选只影响证据。'}
          </div>
          {evidenceError && <Callout tone="danger" title="读取证据失败">{evidenceError}</Callout>}
          <div className="table-scroll evidence-scroll" tabIndex={0} role="region" aria-label="证据列表，可横向滚动">
            <table>
              <thead><tr><th>回合 / 时间</th><th>玩家</th><th>类型 / 武器</th><th>判定</th><th>依据与限制</th></tr></thead>
              <tbody>
                {evidence.map(row => (
                  <tr key={row.evidence_id} className="clickable" tabIndex={0} onClick={() => setDetail(row)} onKeyDown={event => { if (event.key === 'Enter') setDetail(row); }}>
                    <td><strong>{row.round_id}</strong><small>{row.tick} → {row.end_tick ?? row.tick}</small></td>
                    <td>{playerName(row.player_id)}</td>
                    <td>{evidenceKindText(row.kind)}<small>{row.weapon || '武器未知'}</small></td>
                    <td><span className={'pill ' + judgementTone(row.judgement)}>{JUDGEMENT_LABELS[row.judgement] || row.judgement || '观测'}</span></td>
                    <td className="reason">{evidenceReasonText(row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {evidenceLoading && <div className="evidence-loading"><Spinner label="正在读取证据…" /></div>}
          {!evidenceLoading && !evidence.length && (
            <div className="evidence-empty">
              <p>{activeFilterCount ? '当前筛选没有证据。' : '这个模块暂时没有证据记录。'}</p>
              <small>不会生成模拟样本；可以清除筛选或换一名玩家再看。</small>
              {activeFilterCount > 0 && <button type="button" onClick={clearFilters}>清除筛选</button>}
            </div>
          )}
        </section>
      )}

      {prefs.moduleStatus && (
        <div className="capability-strip">
          {Object.entries(result.modules).map(([id, value]: [string, any]) => (
            <button key={id} type="button" className={moduleId === id ? 'active' : ''} onClick={() => onModule(id)}>
              {modules.find(item => item.id === id)?.title || id}<Badge status={value.status} />
            </button>
          ))}
        </div>
      )}

      {detail && (
        <EvidenceDetail detail={detail} players={result.players} onClose={() => setDetail(null)}
          onReplay={focus => onReplay(focus)} technicalDetails={prefs.technicalDetails} />
      )}
    </div>
  );
}
