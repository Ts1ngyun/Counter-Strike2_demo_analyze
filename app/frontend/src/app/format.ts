export type Obj = Record<string, any>;

export type Metric = {
  metric_id: string;
  module_id?: string;
  value: number | null;
  unit: string;
  quality: string;
  coverage: number | null;
  numerator: number | null;
  denominator: number | null;
  eligible_count: number;
  evaluated_count: number;
  unknown_count: number;
  excluded_count: number;
  scope: Obj;
  definition?: Obj;
  parameter_snapshot?: Obj;
  evidence_refs?: string[];
  evidence_count?: number;
  aggregation?: string;
  demo_count?: number;
  unavailable_demos?: number;
  limitations?: string[];
  sample_unit?: string;
};

export type Job = {
  id: string;
  demo_hash: string;
  filename: string;
  status: string;
  stage: string;
  detail?: string | null;
  error?: string | null;
  created: number;
  updated: number;
  map_name?: string | null;
  patch_version?: string | null;
};

export type Result = {
  job_id: string;
  demo: Obj;
  players: Obj[];
  rounds: Obj[];
  modules: Record<string, Obj>;
  config: {modules: string[]; parameters: Obj; players: string[]};
  performance: Obj;
  limitations?: string[];
  capabilities?: Obj;
  fields?: Obj;
  contract_version?: number;
};

export type RoundStatRow = {
  round_id: string;
  player_id: string;
  team: number | null;
  values: Obj;
  metrics: Metric[];
};

export type RoundStatsResponse = {schema_version: number; total: number; rows: RoundStatRow[]};

export const statusTextMap: Record<string, string> = {
  planned: '规划中',
  queued: '排队中',
  running: '分析中',
  succeeded: '完成',
  partial: '部分可用',
  unsupported: '数据不支持',
  failed: '失败',
  cancelled: '已取消',
};

export const qualityTextMap: Record<string, string> = {
  observed: '观测事实',
  derived: '计算得出',
  estimated: '估计值',
  unknown: '暂不可用',
};

export const phaseTextMap: Record<string, string> = {
  official: '正式回合',
  warmup: '热身',
  restart: '重开',
  incomplete: '不完整',
  unscored: '未计分',
  score_unknown: '比分未知',
  score_reset: '比分回退',
  score_ambiguous: '比分不一致',
};

const reasonText: Record<string, string> = {
  warmup: '热身阶段，不进入统计。',
  restart: '比赛重开，不进入统计。',
  incomplete: '回合边界或录像数据不完整。',
  unscored: '没有让最终比分增加，未计分。',
  score_unknown: '比分记录缺失或冲突，无法确认是否计分。',
  score_reset: '比分出现回退，不能按正常回合计分。',
  score_ambiguous: '比分变化超过 1 分，无法确认归属。',
};

export function statusText(status: string): string {
  return statusTextMap[status] || status;
}

export function statusTone(status: string): string {
  if (['succeeded', 'observed', 'ready', 'in_band', 'reasonable'].includes(status)) return 'ok';
  if (['partial', 'estimated', 'ambiguous', 'unreviewed', 'uncertain'].includes(status)) return 'warn';
  if (['failed', 'moving', 'problem'].includes(status)) return 'danger';
  if (['running', 'queued'].includes(status)) return 'info';
  if (['derived'].includes(status)) return 'accent';
  return 'neutral';
}

export function qualityText(quality: string): string {
  return qualityTextMap[quality] || quality;
}

export function phaseText(phase: string): string {
  return phaseTextMap[phase] || phase;
}

export function exclusionText(reason: string | null | undefined): string {
  if (!reason) return '没有给出排除原因。';
  return reasonText[reason] || '排除原因：' + reason + '。';
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return value.toLocaleString('zh-CN', {maximumFractionDigits: digits, minimumFractionDigits: 0});
}

export function unitLabel(unit: string | undefined): string {
  const map: Record<string, string> = {
    seconds: '秒',
    ratio: '%',
    count: '次',
    degrees: '°',
    'hp/round': '伤害 / 回合',
    'hp': '生命值',
    'per_round': '次 / 回合',
    'kills/death': '',
    'events/fire': '次 / 开火',
    units: '距离单位',
  };
  return unit ? (map[unit] || '') : '';
}

export function formatFixed(value: number | null | undefined, digits: number): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return value.toLocaleString('zh-CN', {minimumFractionDigits: digits, maximumFractionDigits: digits});
}

export function coverageText(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '覆盖率未知';
  if (value >= 1) return '全部样本可计算';
  if (value < 1 && value * 100 >= 99.95) return '可计算样本不足 100%';
  return '约 ' + formatNumber(value * 100, 1) + '% 的样本可计算';
}

export function coverageChipText(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '覆盖率未知';
  if (value >= 1) return '覆盖 100%';
  if (value * 100 >= 99.95) return '覆盖 <100%';
  return '覆盖 ' + formatNumber(value * 100, 1) + '%';
}

export type MetricDisplay = {text: string; suffix: string; unavailable: string | null};

export function metricDisplay(metric: Metric | null | undefined): MetricDisplay {
  if (!metric) return {text: '—', suffix: '', unavailable: '没有这项数据。'};
  const value = metric.value;
  if (value === null || value === undefined || typeof value !== 'number' || !Number.isFinite(value)) {
    let reason = '当前数据不足，暂时算不出。';
    if (metric.denominator === 0) reason = '没有符合条件的样本，因此不能算成 0。';
    else if (metric.evaluated_count === 0) reason = '没有可可靠计算的样本。';
    else if (metric.unknown_count > 0) reason = '有 ' + metric.unknown_count + ' 项数据无法确认，这一项暂不计算。';
    else if (metric.quality === 'unknown') reason = '这项数据无法可靠计算。';
    return {text: '—', suffix: '', unavailable: reason};
  }
  if (metric.unit === 'ratio' && metric.metric_id !== 'kd') {
    return {text: formatNumber(value * 100, 1), suffix: '%', unavailable: null};
  }
  if (metric.unit === 'pp/round') return {text:(value>0?'+':'')+formatNumber(value,2),suffix:' pp',unavailable:null};
  if (metric.unit === 'index') return {text:formatFixed(value,2),suffix:'',unavailable:null};
  if (metric.unit === 'degrees') return {text: formatNumber(value, 1), suffix: '°', unavailable: null};
  if (metric.unit === 'seconds') return {text: formatNumber(value, 2), suffix: ' 秒', unavailable: null};
  if (metric.unit === 'units') return {text: formatNumber(value, 0), suffix: ' 单位', unavailable: null};
  if (metric.metric_id === 'kd' || metric.unit === 'kills/death') return {text: formatFixed(value, 2), suffix: '', unavailable: null};
  if (metric.unit === 'per_round') return {text: formatFixed(value, 2), suffix: '', unavailable: null};
  if (metric.unit === 'hp/round') return {text: formatNumber(value, 1), suffix: '', unavailable: null};
  if (metric.unit === 'hp') return {text: formatNumber(value, 0), suffix: '', unavailable: null};
  if (metric.unit === 'events/fire') return {text: formatNumber(value, 3), suffix: '', unavailable: null};
  if (metric.unit === 'count') return {text: formatNumber(value, 0), suffix: '', unavailable: null};
  if (!metric.unit) return {text: formatNumber(value, 2), suffix: '', unavailable: null};
  return {text: formatNumber(value, 2), suffix: ' ' + metric.unit, unavailable: null};
}

export function formatDate(timestamp: number | undefined, withTime = true): string {
  if (!timestamp) return '时间未知';
  const date = new Date(timestamp * 1000);
  return date.toLocaleString('zh-CN', {year: 'numeric', month: '2-digit', day: '2-digit', hour: withTime ? '2-digit' : undefined, minute: withTime ? '2-digit' : undefined});
}

export function roundName(round: Obj | undefined): string {
  if (!round) return '全部回合';
  return (round.round_id || '回合') + ' · ' + phaseText(round.phase);
}

const evidenceKindNames: Record<string, string> = {
  round_stats: '回合参与',
  round_swing: 'Round Swing',
  damage: '伤害事件',
  combat_review: '交战片段',
  kill_aim: '击杀前瞄准',
  view_trajectory: '连续射击轨迹',
  head_geometry: '头线几何',
  stop_shooting: '停步 / 开枪',
  movement_to_first_shot: '移动后首枪',
  recoil_control: '连续射击',
  flash: '闪光',
  flash_review: '闪光复盘',
};

export function evidenceKindText(kind: string | undefined): string {
  if (!kind) return '证据';
  return evidenceKindNames[kind] || '证据记录';
}

const evidenceReasonPlain: Record<string, string> = {
  round_stats: '这一回合的击杀、存活和补枪条件进入了基础统计。',
  damage: '记录到一次伤害事件，相关状态通过了该模块的一致性检查。',
  kill_aim: '击杀前窗口采样足够，进入上下瞄准变化的计算。',
  view_trajectory: '连续射击片段采样足够，进入瞄准方向描述。',
  head_geometry: '几何条件满足，进入实验头线估计。',
  stop_shooting: '开枪瞬间的速度状态满足该片段的计算条件。',
  movement_to_first_shot: '移动后第一次开枪的状态满足该片段的计算条件。',
  recoil_control: '连续射击片段满足最少弹数与姿态条件。',
  flash: '闪光与致盲记录通过唯一配对检查。',
  flash_review: '闪光引爆与受影响记录进入逐颗复盘。',
};

export function evidenceReasonText(row: Obj | null | undefined): string {
  if (!row) return '没有可用说明。';
  return evidenceReasonPlain[row.kind] || '这条记录通过了该模块的纳入检查。';
}

export function teamName(team: number | null | undefined): string {
  if (team === 2) return '阵营 2（T）';
  if (team === 3) return '阵营 3（CT）';
  return '阵营未知';
}

export function sameScope(scope: Obj, filters: Obj): boolean {
  return Object.entries(filters).every(([key, value]) => !value || scope[key] === value);
}

export function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}
