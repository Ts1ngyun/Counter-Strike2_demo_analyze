import React, {useState} from 'react';
import Icon from '../ui/Icon';
import {Modal} from '../ui/primitives';
import Explain from '../explain/MetricExplain';
import {evidenceReasonText, formatNumber} from '../app/format';
import type {Obj} from '../app/format';
import {AimEvidence} from '../CombatReview';
import './analysis.css';

const ATTACK_STATUS: Record<string, string> = {
  continuous_attack_samples: '整个观测区间内，攻击输入持续为真。',
  intermittent_attack_samples: '观测到攻击输入间断。',
  unknown: '输入数据不足或不一致。',
};

function curveSegments(rows: Obj[], key: string) {
  const segments: Obj[][] = [];
  let current: Obj[] = [];
  let last: Obj | null = null;
  for (const row of rows) {
    if (typeof row[key] !== 'number' || !Number.isFinite(row[key])) {
      if (current.length) segments.push(current);
      current = [];
      last = null;
      continue;
    }
    if (last && ((row.segment_id !== undefined && row.segment_id !== last.segment_id) || (row.tick - last.tick > 1))) {
      if (current.length) segments.push(current);
      current = [];
    }
    current.push(row);
    last = row;
  }
  if (current.length) segments.push(current);
  return segments;
}

function Chart({rows, threshold, shotTicks = [], hurtTicks = []}: {rows: Obj[]; threshold?: number | null; shotTicks?: number[]; hurtTicks?: number[]}) {
  const keys = ['speed', 'view_pitch', 'view_yaw', 'effective_recoil', 'residual'].filter(key => rows.some(row => typeof row[key] === 'number'));
  const [series, setSeries] = useState('');
  const key = keys.includes(series) ? series : keys[0];
  if (!key) return <p className="muted">没有可绘制的数值轨迹；缺失数据不会补零。</p>;
  const points = rows.filter(row => typeof row[key] === 'number');
  const segments = curveSegments(rows, key);
  const minX = Math.min(...rows.map((row, index) => row.tick ?? index));
  const maxX = Math.max(...rows.map((row, index) => row.tick ?? index));
  let low = Math.min(...points.map(row => row[key]));
  let high = Math.max(...points.map(row => row[key]));
  if (typeof threshold === 'number' && key === 'speed') {
    low = Math.min(low, threshold);
    high = Math.max(high, threshold);
  }
  const x = (value: number) => 52 + (value - minX) / Math.max(1, maxX - minX) * 642;
  const y = (value: number) => 168 - (value - low) / Math.max(0.01, high - low) * 132;
  return (
    <div className="chart">
      <div className="row chart-head">
        <strong>原生采样轨迹</strong>
        <label className="chart-select">曲线
          <select value={key} onChange={event => setSeries(event.target.value)}>
            {keys.map(item => <option key={item} value={item}>{({speed: '速度', view_pitch: '视角上下', view_yaw: '视角左右', effective_recoil: '有效后坐力', residual: '补偿残差'} as Obj)[item] || item}</option>)}
          </select>
        </label>
      </div>
      <svg viewBox="0 0 730 200" role="img" aria-label="按时间步绘制的证据曲线">
        <path d="M52 26V168H700" stroke="var(--chart-grid)" fill="none" />
        {[low, high].map((value, index) => <text key={index} x="2" y={y(value) + 4}>{formatNumber(value, 1)}</text>)}
        {segments.map((segment, index) => (
          <polyline key={index} points={segment.map(row => x(row.tick) + ',' + y(row[key])).join(' ')} fill="none" stroke="var(--chart-1)" strokeWidth="2" />
        ))}
        {shotTicks.filter(tick => tick >= minX && tick <= maxX).map((tick, index) => <line key={'shot' + index} x1={x(tick)} x2={x(tick)} y1="26" y2="168" stroke="var(--warn)" opacity="0.4" strokeWidth="1" />)}
        {hurtTicks.filter(tick => tick >= minX && tick <= maxX).map((tick, index) => <circle key={'hurt' + index} cx={x(tick)} cy="20" r="4" fill="var(--danger)" />)}
        {typeof threshold === 'number' && key === 'speed' && (
          <>
            <line x1="52" x2="700" y1={y(threshold)} y2={y(threshold)} stroke="var(--warn)" strokeDasharray="5 5" />
            <text x="520" y={y(threshold) - 6}>参考阈值 {formatNumber(threshold, 1)}</text>
          </>
        )}
        <text x="52" y="192">时间步 {minX}</text>
        <text x="650" y="192">{maxX}</text>
      </svg>
      <p>橙黄色竖线表示开枪，红色圆点表示受伤。缺失或跨片段不连线。上下角度的正负方向由引擎坐标决定，不等于屏幕准星位置，也不包含鼠标亚帧输入的重建。</p>
    </div>
  );
}

function AimPath({rows}: {rows: Obj[]}) {
  const valid = rows.filter(row => typeof row.relative_yaw === 'number' && typeof row.view_pitch === 'number');
  if (!valid.length) return null;
  const base = valid[0].view_pitch;
  const extent = Math.max(1, ...valid.flatMap(row => [Math.abs(row.relative_yaw), Math.abs(row.view_pitch - base)]));
  const x = (row: Obj) => 260 + row.relative_yaw / extent * 120;
  const y = (row: Obj) => 145 + (row.view_pitch - base) / extent * 120;
  const segments = curveSegments(rows, 'view_pitch');
  return (
    <div className="chart">
      <strong>连续射击瞄准方向轨迹 <Explain term="aim_change" /></strong>
      <svg viewBox="0 0 520 290" role="img" aria-label="连续射击相对视角轨迹">
        <path d="M30 145H490M260 15V270" stroke="var(--chart-grid)" />
        {segments.map((segment, index) => (
          <polyline key={index} points={segment.filter(row => typeof row.relative_yaw === 'number').map(row => x(row) + ',' + y(row)).join(' ')} fill="none" stroke="var(--chart-1)" strokeWidth="2" />
        ))}
        {valid.filter(row => row.shot).map((row, index) => <circle key={index} cx={x(row)} cy={y(row)} r="3" fill="var(--warn)" />)}
        <text x="30" y="282">等比例角度坐标 · 半轴 {formatNumber(extent, 1)}° · 起点 (0, 0)</text>
      </svg>
      <p>起点为零，横轴为左右转角，纵轴为上下转角，两个方向使用相同比例。轨迹混合了跟枪、主动瞄准与可能的后坐力影响，不代表弹着点或压枪准度。</p>
    </div>
  );
}

export default function EvidenceDetail({detail, players, onClose, onReplay, technicalDetails}: {
  detail: Obj;
  players: Obj[];
  onClose: () => void;
  onReplay: (focus: {tick: number; round_id?: string; player_id?: string}) => void;
  technicalDetails: boolean;
}) {
  const playerName = players.find(player => player.player_id === detail.player_id)?.name || detail.player_id;
  return (
    <Modal open onClose={onClose} title={playerName + ' · 时间步 ' + detail.tick} eyebrow={'证据 / ' + detail.round_id} label="证据详情" size="lg"
      footer={<div className="evidence-foot"><button type="button" onClick={() => onReplay({tick: detail.tick, round_id: detail.round_id, player_id: detail.player_id})}><Icon name="play" size={15} />在 2D 回放中定位</button><button type="button" onClick={onClose}>关闭</button></div>}>
      <p className="evidence-reason">{evidenceReasonText(detail)}</p>
      <div className="evidence-meta">
        <span><small>回合</small><strong>{detail.round_id}</strong></span>
        <span><small>时间步</small><strong>{detail.tick}</strong></span>
        <span><small>玩家</small><strong>{playerName}</strong></span>
        {detail.weapon && <span><small>武器</small><strong>{detail.weapon}</strong></span>}
      </div>

      {detail.kind === 'round_swing' && detail.values && <section className="evidence-block">
        <h3>Round Swing · 下包前估算</h3>
        <div className="evidence-stats">
          <span>击杀方人数<strong>{detail.values.own_alive_before} vs {detail.values.enemy_alive_before}</strong></span>
          <span>击杀方模型概率<strong>{formatNumber(detail.values.attacker_probability_before * 100, 2)}% → {formatNumber(detail.values.attacker_probability_after * 100, 2)}%</strong></span>
          <span>该玩家本次变化<strong>{detail.values.signed_percentage_points > 0 ? '+' : ''}{formatNumber(detail.values.signed_percentage_points, 2)} pp</strong></span>
        </div>
        <p className="muted">每次对枪按五五开估算。这里只比较人数优势，不是实际回合胜率。</p>
      </section>}

      {detail.kind === 'kill_aim' && (
        <div className="evidence-block">
          <h3>击杀前瞄准窗口</h3>
          <div className="evidence-stats">
            <span>武器<strong>{detail.weapon || '未知'}</strong></span>
            <span>有效时长<strong>{formatNumber(detail.valid_seconds, 3)} / {formatNumber(detail.requested_seconds)} 秒</strong></span>
            <span>上下幅度（95% 与 5% 分位差）<strong>{formatNumber(detail.pitch_p95_p5, 2)}°</strong></span>
            <span>最大上下差<strong>{formatNumber(detail.pitch_range, 2)}°</strong></span>
          </div>
          {detail.overlapping_window_ids?.length > 0 && <p className="muted">此窗口与另外 {detail.overlapping_window_ids.length} 次击杀重叠，按击杀分别统计。</p>}
        </div>
      )}

      {detail.kind === 'view_trajectory' && (
        <div className="evidence-block">
          <h3>连续射击输入</h3>
          <p>{ATTACK_STATUS[detail.attack_input_status] || '旧版结果：未提取攻击输入。'} 黄点表示开枪采样；这里观察瞄准方向，不评价对手跑跳时的压枪准度。持续观测不等于物理左键持续按下。</p>
        </div>
      )}

      {detail.kind === 'head_geometry' && detail.eye && detail.head && (
        <div className="chart">
          <strong>垂直平面几何 · 示意，非等比例</strong>
          <svg viewBox="0 0 600 170" role="img" aria-label="眼睛与头部高度几何示意">
            <circle cx="60" cy="115" r="5" fill="var(--chart-1)" />
            <circle cx="510" cy="65" r="10" fill="var(--chart-2)" />
            <path d="M60 115H550M60 115L510 65" fill="none" stroke="var(--chart-1)" />
            <path d={'M60 115L510 ' + (115 - 450 * Math.tan(detail.aim_elevation * Math.PI / 180))} stroke="var(--chart-2)" strokeDasharray="5 5" fill="none" />
            <text x="24" y="148">眼位 E · {detail.self_pose}</text>
            <text x="404" y="34">近似头位 H · {detail.target_pose}</text>
          </svg>
          <p>垂直误差 {formatNumber(detail.vertical_error, 1)}° · 水平误差 {formatNumber(detail.horizontal_error, 1)}° · 距离 {formatNumber(detail.distance, 0)} 单位 · 容差 ±{formatNumber(detail.tolerance, 1)}°</p>
        </div>
      )}

      {detail.curve && (
        <>
          <Chart rows={detail.curve} threshold={detail.threshold} shotTicks={detail.shot_ticks} hurtTicks={detail.hurt_ticks} />
          {detail.kind === 'view_trajectory' && <AimPath rows={detail.curve} />}
        </>
      )}

      <AimEvidence row={detail} />

      <p className="evidence-source">来源：{String(detail.demo_hash || '').slice(0, 16)}… · 原生时间分辨率 {formatNumber(detail.native_resolution_seconds * 1000, 3)} 毫秒/时间步 · subtick 与跨类型事件顺序未知。</p>

      <details className="technical-reason">
        <summary>技术判定依据</summary>
        <p>{detail.reason}</p>
      </details>
      <details className="raw-evidence" open={technicalDetails}>
        <summary>原始数值、规则与完整证据</summary>
        <pre>{JSON.stringify(detail, null, 2)}</pre>
      </details>
    </Modal>
  );
}
