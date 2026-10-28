import React, {useMemo, useState} from 'react';
import Icon from '../ui/Icon';
import {Badge, Callout, Coverage, EmptyState} from '../ui/primitives';
import Explain from '../explain/MetricExplain';
import {coverageText, exclusionText, formatDate, formatNumber, metricDisplay, phaseText, statusText} from '../app/format';
import type {Job, Metric, Obj, Result} from '../app/format';
import './overview.css';

const MODULE_BLURB: Record<string, string> = {
  basic_stats: '击杀、死亡、伤害、KAST 与单回合基础统计。',
  combat_review: '把死亡和交火片段按情形标签排成复盘队列。',
  head_line: '击杀、死亡与未击杀交火前后的上下瞄准变化。',
  stop_shooting: '移动后首枪与开枪瞬间的速度状态。',
  recoil_control: '连续射击的视角移动与可描述序列。',
  utility_analysis: '逐颗闪光的引爆、致盲关系与闪后击杀。',
};

const EVENT_LABELS: [string, string][] = [
  ['player_death', '击杀事件'],
  ['flashbang_detonate', '闪光引爆'],
  ['bomb_planted', '下包'],
  ['round_end', '回合结束'],
];

type OpenAnalysis = (options?: {player?: string; round?: string; scope?: 'match' | 'round'; module?: string}) => void;

export default function Overview({
  result, jobs, active, modules, uploading, uploadProgress,
  onUpload, onSelectJob, onOpenAnalysis, onOpenReplay, onOpenJobs,
  onCancel, onRetry, onOpenConfig, technicalDetails,
}: {
  result: Result | null;
  jobs: Job[];
  active: string;
  modules: Obj[];
  uploading: boolean;
  uploadProgress: number;
  onUpload: (files: FileList | File[]) => void;
  onSelectJob: (id: string) => void;
  onOpenAnalysis: OpenAnalysis;
  onOpenReplay: () => void;
  onOpenJobs: () => void;
  onCancel: () => void;
  onRetry: () => void;
  onOpenConfig: () => void;
  technicalDetails: boolean;
}) {
  const [drag, setDrag] = useState(false);
  const [showExcluded, setShowExcluded] = useState(false);
  const job = jobs.find(item => item.id === active);
  const orderedJobs = useMemo(() => [...jobs].sort((a, b) => (b.created || 0) - (a.created || 0)), [jobs]);

  const teams = useMemo(() => {
    if (!result) return [] as {team: number; name: string; score: number}[];
    const map = new Map<number, {team: number; name: string; score: number}>();
    for (const state of result.demo.final_state || []) {
      if (!map.has(state.team_num)) map.set(state.team_num, {team: state.team_num, name: state.team_clan_name || '未知队伍', score: state.team_rounds_total});
    }
    return Array.from(map.values()).sort((a, b) => a.team - b.team);
  }, [result]);

  const coreMetrics = useMemo(() => {
    const map = new Map<string, Metric>();
    for (const metric of result?.modules?.basic_stats?.metrics || []) {
      if (metric.scope?.player_id && !metric.scope.weapon && !metric.scope.team && !metric.scope.self_pose && !metric.scope.distance_bucket) {
        const key = metric.scope.player_id + ':' + metric.metric_id;
        if (!map.has(key)) map.set(key, metric);
      }
    }
    return map;
  }, [result]);

  const metricFor = (playerId: string, metricId: string): Metric | null => coreMetrics.get(playerId + ':' + metricId) || null;
  const counts = result?.demo?.event_inventory?.counts || {};
  const includedRounds = result?.rounds?.filter(round => round.complete) || [];
  const excludedRounds = result?.rounds?.filter(round => !round.complete) || [];
  const players = result?.players || [];

  const uploadCard = (
    <div
      className={'upload-card' + (drag ? ' drag' : '') + (uploading ? ' busy' : '')}
      onDragOver={event => { event.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={event => {
        event.preventDefault();
        setDrag(false);
        if (!uploading && event.dataTransfer.files?.length) onUpload(event.dataTransfer.files);
      }}
    >
      <span className="upload-icon"><Icon name="upload" size={22} /></span>
      <div className="upload-copy">
        <strong>{uploading ? '正在传输 demo…' : '拖入 .dem，开始本地分析'}</strong>
        <p>多文件排队 · 相同内容按 SHA-256 去重 · 原始文件不离开本机</p>
        {uploading && <div className="upload-progress" aria-label={'上传进度 ' + Math.round(uploadProgress * 100) + '%'}><i style={{width: Math.max(2, Math.round(uploadProgress * 100)) + '%'}} /></div>}
      </div>
      <label className="button primary upload-button">
        选择文件
        <input type="file" multiple accept=".dem" hidden disabled={uploading} onChange={event => { if (event.target.files?.length) onUpload(event.target.files); event.target.value = ''; }} />
      </label>
    </div>
  );

  if (!result) {
    return (
      <div className="overview">
        <section className="start-hero">
          <div className="start-copy">
            <span className="eyebrow">COUNTER-STRIKE 2 / LOCAL EVIDENCE</span>
            <h2>导入 Demo，<br />开始复盘。</h2>
            <p>查看比赛数据、交战片段与 2D 回放。分析在本机完成。</p>
            <div className="start-points">
              <span><Icon name="check" size={15} /> 离线分析，无需账号</span>
              <span><Icon name="check" size={15} /> 未知不补零</span>
              <span><Icon name="check" size={15} /> 每个指标都有小白解释</span>
            </div>
            <div className="start-actions">
              <button type="button" className="primary" onClick={onOpenConfig}>先看分析配置</button>
              <button type="button" onClick={onOpenJobs}>打开任务队列</button>
            </div>
          </div>
          <div className="start-visual" aria-hidden="true">
            <svg className="tactical-plan" viewBox="0 0 440 320" fill="none">
              <g stroke="currentColor" strokeWidth="1.5"><path d="M40 55H190V95H245V30H385V130H340V195H390V285H230V230H160V275H40Z"/><path d="M60 75H170V115H265V50H365V110H320V215H370V265H250V210H140V255H60Z"/><path d="M95 75V165H170V115M265 50V160H320M140 210V185H220V265M60 205H140M310 215V265"/></g>
              <path d="M92 235V185H190V145H290V80" stroke="var(--accent-2)" strokeWidth="3" strokeDasharray="7 7"/>
              <g fill="var(--accent)" stroke="currentColor"><circle cx="92" cy="235" r="7"/><circle cx="290" cy="80" r="7"/></g>
              <g fill="currentColor" fontSize="12" fontFamily="monospace"><text x="90" y="105">A / SECTOR</text><text x="278" y="247">B / SECTOR</text><text x="40" y="310">TACTICAL STUDY — NOT MATCH DATA</text></g>
            </svg>
            <div className="visual-ring ring-a" />
            <div className="visual-ring ring-b" />
            <div className="visual-cross" />
            <span className="visual-label top">战术空间 / 示意</span>
            <span className="visual-label mid">复盘路径</span>
            <span className="visual-label bottom">LOCAL ANALYSIS</span>
          </div>
        </section>
        {uploadCard}
        <section className="start-steps">
          {[
            ['01', '导入原始文件', '拖入 .dem。文件哈希用于去重，解析在本机进行。'],
            ['02', '等待逐模块完成', '基础统计、交战复盘、瞄准、急停、压枪与闪光分别计算；失败会隔离到单个模块。'],
            ['03', '从结论回到证据', '先看概览与关键指标，再点开证据抽屉或 2D 回放定位到具体时间点。'],
          ].map(([number, title, text]) => (
            <article className="step-card" key={number}>
              <span className="step-number">{number}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </section>
        <section className="panel module-overview">
          <div className="section-head"><div><h2>分析模块</h2><p>选择需要分析的模块。</p></div></div>
          <div className="module-grid">
            {modules.filter(module => module.enabled).map(module => (
              <article className="module-tile" key={module.id}>
                <div className="module-tile-head"><h3>{module.title}</h3><Badge status={module.status} /></div>
                <p>{MODULE_BLURB[module.id] || '已启用模块'}</p>
              </article>
            ))}
          </div>
          {modules.some(module => !module.enabled) && (
            <details className="planned">
              <summary>开发计划（未实现，不会产生结果）</summary>
              <div className="planned-list">
                {modules.filter(module => !module.enabled).map(module => (
                  <div key={module.id}><strong>{module.title}</strong><span>规划中</span></div>
                ))}
              </div>
            </details>
          )}
        </section>
        {!!jobs.length && (
          <section className="panel">
            <div className="section-head"><div><h2>已有任务</h2><p>上次的分析结果仍在本地，可以直接打开。</p></div><button type="button" onClick={onOpenJobs}>全部任务</button></div>
            <div className="recent-job-list">
              {orderedJobs.slice(0, 5).map(item => (
                <button type="button" className={'recent-job' + (item.id === active ? ' active' : '')} key={item.id} onClick={() => onSelectJob(item.id)}>
                  <span className="recent-job-file">{item.filename}</span>
                  <span className="recent-job-meta">{item.map_name || '地图未知'} · {formatDate(item.updated)}</span>
                  <Badge status={item.status} />
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    );
  }

  const running = job && ['queued', 'running'].includes(job.status);

  return (
    <div className="overview">
      <section className="match-hero">
        <div className="match-hero-main">
          <div className="report-label"><span>比赛档案</span><span>MATCH REPORT / CS2</span></div>
          <span className="eyebrow">{result.demo.header?.map_name || '未知地图'} · PATCH {result.demo.header?.patch_version || '未知'}</span>
          <div className="scoreboard">
            {teams.length ? teams.map(team => (
              <div className={'score-team team-' + team.team} key={team.team}>
                <span className="score-name">{team.name}</span>
                <strong className="score-value">{formatNumber(team.score, 0)}</strong>
              </div>
            )) : <div className="score-team"><span className="score-name">比分不可用</span><strong className="score-value">—</strong></div>}
          </div>
          <p className="score-note">
            录像记录的最终队伍比分 <Explain term="raw_score" /> · 纳入分析 {includedRounds.length} 个完整正式回合
            {excludedRounds.length > 0 && <> · 另有 {excludedRounds.length} 个回合未计入</>}
          </p>
          <div className="match-actions">
            <button type="button" className="primary" onClick={() => onOpenAnalysis({scope: 'match'})}><Icon name="pulse" size={16} />查看比赛分析</button>
            <button type="button" onClick={onOpenReplay}><Icon name="play" size={15} />打开 2D 回放</button>
            <button type="button" className="ghost" onClick={onOpenJobs}><Icon name="stack" size={15} />任务与数据</button>
          </div>
        </div>
        <div className="match-facts">
          <div><span>完整正式回合</span><strong>{includedRounds.length}</strong><small>进入统计分母</small></div>
          <div><span>玩家</span><strong>{players.length}</strong><small>按 SteamID 识别</small></div>
          <div><span>击杀事件</span><strong>{formatNumber(counts.player_death, 0)}</strong><small>录像原始计数</small></div>
          <div><span>录像时长</span><strong>{result.demo.container?.playback_seconds ? formatNumber(result.demo.container.playback_seconds / 60, 0) : '—'}<em>分</em></strong><small>按实际录像时间</small></div>
          {technicalDetails && <div><span>分析耗时</span><strong>{formatNumber(result.performance?.wall_seconds, 1)}<em>s</em></strong><small>{result.performance?.facts_cache_hit ? '复用事实缓存' : '本次运行'}</small></div>}
          {technicalDetails && <div><span>峰值内存</span><strong>{formatNumber((result.performance?.peak_sampled_worker_rss_bytes || 0) / 1024 ** 2, 0)}<em>MB</em></strong><small>采样峰值，不是上限</small></div>}
        </div>
      </section>

      {running && (
        <Callout tone="info" title={job?.status === 'queued' ? '任务在排队' : '正在分析'}
          action={<><button type="button" onClick={onCancel}>取消任务</button></>}>
          {job?.stage || '等待工作进程'}。{job?.detail ? <span className="muted"> {String(job.detail).split(String.fromCharCode(10))[0]}</span> : null}
        </Callout>
      )}

      <section className="event-strip" aria-label="录像事件摘要">
        {EVENT_LABELS.map(([key, label]) => (
          typeof counts[key] === 'number' ? (
            <div className="event-stat" key={key}>
              <strong>{formatNumber(counts[key], 0)}</strong>
              <span>{label}</span>
            </div>
          ) : null
        ))}
        <div className="event-stat wide">
          <strong>{result.demo.header?.server_name || '本地录像'}</strong>
          <span>录像服务器</span>
        </div>
      </section>

      <section className="panel rounds-panel">
        <div className="section-head">
          <div><h2>回合脉络</h2><p>每个方块是一个计入统计的回合。数字是录像记录的双方累计总比分，不是某一队的比分。</p></div>
          <button type="button" className="ghost" onClick={() => setShowExcluded(value => !value)} aria-expanded={showExcluded}>
            未计入回合 · {excludedRounds.length}
          </button>
        </div>
        <div className="round-strip" role="list" aria-label="回合列表">
          {result.rounds.map(round => {
            const display = String(round.score_after_total ?? '—');
            return (
              <button
                type="button"
                role="listitem"
                key={round.round_id}
                className={'round-chip' + (round.complete ? '' : ' excluded')}
                aria-label={round.round_id + '，胜方 ' + (round.winner || '未知') + '，累计比分 ' + display + (round.complete ? '' : '，未计入')}
                onClick={() => onOpenAnalysis({round: round.round_id, scope: 'round'})}
              >
                <span className="round-id">{round.round_id}</span>
                <span className="round-winner">{round.winner ? round.winner + ' 胜' : phaseText(round.phase)}</span>
                <strong>{display}</strong>
              </button>
            );
          })}
        </div>
        {showExcluded && (
          <div className="excluded-list">
            {excludedRounds.length ? excludedRounds.map(round => (
              <div className="excluded-item" key={round.round_id}>
                <strong>{round.round_id}</strong>
                <span>{phaseText(round.phase)}</span>
                <p>{exclusionText(round.exclusion_reason || round.reason)}</p>
              </div>
            )) : <p className="muted">这场 demo 没有未计入的回合。所有回合都通过了比分与边界检查。</p>}
            <p className="muted">未计分回合不是“零表现”；它们只是不进入统计分母。</p>
          </div>
        )}
      </section>

      <div className="team-grid">
        {teams.map(team => {
          const roster = players.filter(player => player.team_number === team.team);
          return (
            <section className="panel team-card" key={team.team}>
              <header className="team-head">
                <div><span className={'team-dot team-' + team.team} aria-hidden="true" /><h2>{team.name}</h2></div>
                <span className="team-score-small">{formatNumber(team.score, 0)}</span>
              </header>
              <div className="team-table-scroll" tabIndex={0} role="region" aria-label="队伍球员表，可横向滚动">
                <table className="team-table">
                  <thead>
                    <tr><th>玩家</th><th>击杀</th><th>死亡</th><th>K/D <Explain metricId="kd" /></th><th>每回合伤害 <Explain metricId="adr_raw" /></th><th>KAST <Explain metricId="kast_local" /></th></tr>
                  </thead>
                  <tbody>
                    {roster.map(player => {
                      const kills = metricFor(player.player_id, 'kills');
                      const deaths = metricFor(player.player_id, 'deaths');
                      const kd = metricFor(player.player_id, 'kd');
                      const adr = metricFor(player.player_id, 'adr_raw');
                      const kast = metricFor(player.player_id, 'kast_local');
                      return (
                        <tr key={player.player_id} onClick={() => onOpenAnalysis({player: player.player_id, scope: 'match'})} className="clickable">
                          <td><button type="button" className="player-name" onClick={event => { event.stopPropagation(); onOpenAnalysis({player: player.player_id, scope: 'match'}); }}>{player.name}</button>{technicalDetails && <small>{player.player_id}</small>}</td>
                          <td className="num">{kills ? metricDisplay(kills).text + metricDisplay(kills).suffix : '—'}</td>
                          <td className="num">{deaths ? metricDisplay(deaths).text + metricDisplay(deaths).suffix : '—'}</td>
                          <td className="num">{kd ? metricDisplay(kd).text + metricDisplay(kd).suffix : '—'}</td>
                          <td className="num">{adr ? metricDisplay(adr).text + metricDisplay(adr).suffix : '—'}{adr && adr.value === null && <small>暂不可用</small>}</td>
                          <td className="num">{kast ? metricDisplay(kast).text + metricDisplay(kast).suffix : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <button type="button" className="team-open" onClick={() => onOpenAnalysis({player: roster[0]?.player_id, scope: 'match'})}>查看个人指标 <Icon name="arrow-right" size={15} /></button>
            </section>
          );
        })}
      </div>

      <section className="panel">
        <div className="section-head">
          <div><h2>分析模块</h2><p>已实现模块与当前结果状态。点击进入模块工作区。</p></div>
          <button type="button" onClick={onOpenConfig}>调整参数</button>
        </div>
        <div className="module-grid">
          {modules.filter(module => module.enabled).map(module => {
            const moduleResult = result.modules[module.id];
            return (
              <article className="module-tile" key={module.id}>
                <div className="module-tile-head">
                  <h3>{module.title}</h3>
                  <Badge status={moduleResult?.status || 'unsupported'} />
                </div>
                <p>{MODULE_BLURB[module.id] || '已启用模块'}</p>
                <div className="module-tile-foot">
                  <small>{moduleResult ? (moduleResult.metrics?.length || 0) + ' 项指标' : '本次未运行'}</small>
                  <button type="button" onClick={() => onOpenAnalysis({module: module.id})}>打开 <Icon name="arrow-right" size={14} /></button>
                </div>
                {moduleResult?.status === 'partial' && (
                  <span className="module-partial">部分可用 <Explain term="partial" /></span>
                )}
              </article>
            );
          })}
        </div>
        {modules.some(module => !module.enabled) && (
          <details className="planned">
            <summary>开发计划（未实现，不会产生结果）</summary>
            <div className="planned-list">
              {modules.filter(module => !module.enabled).map(module => (
                <div key={module.id}><strong>{module.title}</strong><span>规划中</span></div>
              ))}
            </div>
          </details>
        )}
      </section>

      <section className="boundary-grid">
        <article className="boundary-card good">
          <h3><Icon name="check" size={17} />这份报告可以回答</h3>
          <ul>
            <li>这场比赛的回合是否计入了统计，以及为什么。</li>
            <li>每个玩家的击杀、伤害、KAST 和单回合表现。</li>
            <li>某个片段发生在哪一回合、哪个时间点，并回到 2D 回放。</li>
          </ul>
        </article>
        <article className="boundary-card bad">
          <h3><Icon name="warning" size={17} />这份报告不能回答</h3>
          <ul>
            <li>官方 Rating 与职业选手排名。</li>
            <li>玩家屏幕里真实看到了什么，或子弹是否一定命中。</li>
            <li>规划中的定位、选位能力；它们还没有实现。</li>
          </ul>
        </article>
      </section>

      {uploadCard}

      <section className="panel">
        <div className="section-head"><div><h2>最近任务</h2><p>同内容 demo 会复用本机解析结果。</p></div><button type="button" onClick={onOpenJobs}>全部任务</button></div>
        <div className="recent-job-list">
          {orderedJobs.slice(0, 4).map(item => (
            <button type="button" className={'recent-job' + (item.id === active ? ' active' : '')} key={item.id} onClick={() => onSelectJob(item.id)}>
              <span className="recent-job-file">{item.filename}</span>
              <span className="recent-job-meta">{item.map_name || '地图未知'} · {formatDate(item.updated)}</span>
              <Badge status={item.status} />
            </button>
          ))}
        </div>
        {job && ['failed', 'cancelled'].includes(job.status) && (
          <Callout tone="danger" title="当前任务没有完成" action={<button type="button" onClick={onRetry}>重试</button>}>
            {job.error || '任务被取消或失败。可以重试；已缓存的事实会尽量复用。'}
          </Callout>
        )}
      </section>
    </div>
  );
}
