import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import type {Metric, Obj} from '../app/format';
import {coverageText, metricDisplay, qualityText} from '../app/format';
import {glossaryCopy, metricCopy, metricName} from './dictionary';
import './explain.css';

export const PARAM_NAMES: Record<string, string> = {
  trade_seconds: '补枪窗口（秒）',
  window_start_ms: '候选窗口起点（毫秒）',
  window_end_ms: '候选窗口终点（毫秒）',
  horizontal_cone_deg: '水平候选锥角（度）',
  eye_stand: '站立眼高（模型单位）',
  eye_duck: '蹲伏眼高（模型单位）',
  head_stand: '站立头高（模型单位）',
  head_duck: '蹲伏头高（模型单位）',
  head_radius: '头部半径（模型单位）',
  flash_exclude_seconds: '致盲排除阈值（秒）',
  threshold_scale: '武器速度阈值倍率',
  movement_lookback_ms: '移动回看窗口（毫秒）',
  movement_min_ms: '最低运动时长（毫秒）',
  movement_enter_multiplier: '运动进入滞回倍率',
  boundary_margin: '边界模糊带（速度单位）',
  min_burst_shots: '最小连续射击弹数',
  pose_change_limit: '姿态变化排除阈值',
  kill_min_coverage: '击杀窗口最低覆盖率',
  before_death_seconds: '死亡前片段（秒）',
  after_death_seconds: '死亡后片段（秒）',
  engagement_gap_seconds: '交战切分间隔（秒）',
  speed_margin: '速度余量',
  kill_window_seconds: '闪后击杀关联窗口（秒）',
};

type ExplainProps = {
  metricId?: string;
  term?: string;
  definition?: Obj;
  metric?: Metric | null;
  title?: string;
  compact?: boolean;
  inline?: boolean;
  align?: 'left' | 'right';
};

export default function Explain({metricId, term, definition, metric, title, compact, inline}: ExplainProps) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState({left: 0, top: 0, bottom: null as number | null, width: 380, above: false, maxHeight: 520});
  const trigger = useRef<HTMLButtonElement | null>(null);
  const popover = useRef<HTMLDivElement | null>(null);
  const closeTimer = useRef<number | null>(null);

  const copy = metricId ? metricCopy(metricId, definition) : glossaryCopy(term || '');
  const resolvedTitle = title || (metricId ? metricName(metricId, definition) : copy.name);
  const display = metric ? metricDisplay(metric) : null;

  function place() {
    const button = trigger.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const width = Math.min(392, window.innerWidth - 24);
    const margin = 12;
    let left = rect.left;
    if (left + width > window.innerWidth - margin) left = rect.right - width;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
    const spaceBelow = window.innerHeight - rect.bottom - 16;
    const spaceAbove = rect.top - 16;
    const above = spaceBelow < 340 && spaceAbove > spaceBelow;
    const maxHeight = Math.max(220, Math.min(560, (above ? spaceAbove : spaceBelow) - 6));
    setPosition({left, top: above ? 0 : rect.bottom + 8, bottom: above ? window.innerHeight - rect.top + 8 : null, width, above, maxHeight});
  }

  useLayoutEffect(() => {
    if (!open) return;
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (trigger.current?.contains(target) || popover.current?.contains(target)) return;
      setPinned(false);
      setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPinned(false);
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => () => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
  }, []);

  const show = (delay = 0) => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(true), delay);
  };
  const hide = () => {
    if (pinned) return;
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={'explain-trigger' + (compact ? ' compact' : '') + (inline ? ' inline' : '')}
        aria-label={'怎么理解：' + resolvedTitle}
        aria-expanded={open}
        aria-haspopup="dialog"
        onMouseEnter={() => show(80)}
        onMouseLeave={hide}
        onFocus={() => setOpen(true)}
        onBlur={() => { if (!pinned) setOpen(false); }}
        onClick={event => {
          event.preventDefault();
          event.stopPropagation();
          const next = !(open && pinned);
          setPinned(next);
          setOpen(next);
        }}
      ><span aria-hidden="true">?</span></button>
      {open && createPortal(
        <div
          ref={popover}
          className={'explain-pop glass' + (position.above ? ' above' : '')}
          style={{left: position.left, width: position.width, maxHeight: position.maxHeight, ...(position.above ? {bottom: position.bottom ?? 0} : {top: position.top})}}
          role="dialog"
          aria-label={resolvedTitle + ' 说明'}
          onMouseEnter={() => { if (closeTimer.current) window.clearTimeout(closeTimer.current); }}
          onMouseLeave={hide}
        >
          <div className="explain-head">
            <div>
              <span className="eyebrow">指标说明</span>
              <h3>{resolvedTitle}</h3>
            </div>
            <button type="button" className="explain-close" aria-label="关闭说明" onClick={() => { setPinned(false); setOpen(false); }}>×</button>
          </div>
          <p className="explain-lead">{copy.oneLine}</p>
          {metric?.quality === 'estimated' && <p className="explain-estimate">估算值 · 非官方指标</p>}
          <details className="explain-details">
            <summary>公式与补充说明</summary>
            {copy.example && <p>{copy.example}</p>}
            {copy.cannot && <p>{copy.cannot}</p>}
            {metric && <p>当前值：{display?.text}{display?.suffix} · {qualityText(metric.quality)} · {coverageText(metric.coverage)}</p>}
            <dl>
              {definition?.formula && <><dt>公式</dt><dd>{definition.formula}</dd></>}
              {definition?.inclusion && <><dt>纳入</dt><dd>{definition.inclusion}</dd></>}
              {definition?.exclusion && <><dt>排除</dt><dd>{definition.exclusion}</dd></>}
              {definition?.numerator_denominator && <><dt>分母与样本</dt><dd>{definition.numerator_denominator}</dd></>}
              {definition?.time_requirements && <><dt>时间要求</dt><dd>{definition.time_requirements}</dd></>}
              {definition?.limitations && <><dt>已知局限</dt><dd>{definition.limitations}</dd></>}
              {metric && <><dt>本次统计</dt><dd>{metric.denominator !== null && metric.denominator !== undefined ? '分子 ' + (metric.numerator ?? '—') + ' / 分母 ' + metric.denominator : '有效样本 ' + metric.evaluated_count}，未知 {metric.unknown_count}，排除 {metric.excluded_count}。</dd></>}
              {metric?.parameter_snapshot && Object.keys(metric.parameter_snapshot).length > 0 && <><dt>当前参数</dt><dd>{Object.entries(metric.parameter_snapshot).map(([key, value]) => (PARAM_NAMES[key] || key) + '：' + String(value)).join('；')}</dd></>}
            </dl>
            {!definition?.formula && !copy.detail && <p className="muted">这份结果没有附带完整公式；请以当前分析版本的指标定义为准。</p>}
          </details>
        </div>,
        document.body,
      )}
    </>
  );
}

export function Term({children, term, metricId, definition}: {children?: React.ReactNode; term?: string; metricId?: string; definition?: Obj}) {
  return (
    <span className="term">
      {children}
      <Explain term={term} metricId={metricId} definition={definition} compact />
    </span>
  );
}
