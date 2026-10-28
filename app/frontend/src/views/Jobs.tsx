import React, {useEffect, useState} from 'react';
import Icon from '../ui/Icon';
import {Badge, Callout, EmptyState, Field, Modal, Segmented, Spinner} from '../ui/primitives';
import Explain from '../explain/MetricExplain';
import {metricName} from '../explain/dictionary';
import {api} from '../app/api';
import {coverageText, formatDate, formatNumber, metricDisplay, statusText} from '../app/format';
import type {Job, Metric, Obj, Result} from '../app/format';
import './jobs.css';

function formatBytes(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  if (value < 1024) return value + ' B';
  if (value < 1024 ** 2) return (value / 1024).toFixed(1) + ' KiB';
  if (value < 1024 ** 3) return (value / 1024 ** 2).toFixed(1) + ' MiB';
  return (value / 1024 ** 3).toFixed(2) + ' GiB';
}

const TABLES = ['commands', 'fields', 'raw_fields', 'capabilities', 'events', 'rounds', 'players', 'player_states', 'weapon_states', 'shots', 'bursts', 'engagements', 'movement'];

const MODULE_TITLES: Record<string, string> = {basic_stats: '基础比赛统计', combat_review: '交战与死亡复盘', head_line: '交战瞄准变化', stop_shooting: '急停与停步开枪', recoil_control: '连续射击与压枪', utility_analysis: '闪光弹分析'};
const SCOPE_NAMES: Record<string, string> = {weapon: '武器', weapon_set: '武器范围', analysis_mode: '分析视图', team: '阵营', self_pose: '姿态', distance_bucket: '距离', grounded: '地面状态'};

export default function Jobs({jobs, active, result, onSelect, onCancel, onRetry, onOpenAnalysis, chosenJobs, setChosenJobs, aggregate, setAggregate, fullCoverage, technicalDetails}: {
  jobs: Job[];
  active: string;
  result: Result | null;
  onSelect: (id: string) => void;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
  onOpenAnalysis: (jobId: string, playerId?: string) => void;
  chosenJobs: string[];
  setChosenJobs: (ids: string[]) => void;
  aggregate: Obj | null;
  setAggregate: (value: Obj | null) => void;
  fullCoverage: boolean;
  technicalDetails: boolean;
}) {
  const [section, setSection] = useState('queue');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [storage, setStorage] = useState<Obj | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [table, setTable] = useState('events');
  const [tick, setTick] = useState('');
  const [inspection, setInspection] = useState<any>(null);
  const [inspectionBusy, setInspectionBusy] = useState(false);
  const ordered = [...jobs].sort((a, b) => (b.created || 0) - (a.created || 0));
  const job = jobs.find(item => item.id === active);

  useEffect(() => {
    if (section !== 'storage') return;
    api('/storage').then(setStorage).catch(error => setError(error.message));
  }, [section]);

  async function aggregateSelected() {
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await api('/aggregate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job_ids: chosenJobs})});
      setAggregate(data);
      setMessage('已按总分子 / 总分母合并；同哈希只计一次。');
    } catch (error: any) {
      setError(error.message || String(error));
    } finally {
      setBusy(false);
    }
  }

  async function removeCopy() {
    if (!result) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await api('/uploads/' + result.demo.demo_hash, {method: 'DELETE'});
      setStorage(await api('/storage'));
      setMessage('已清理应用内原始副本；高频事实与结果仍可复查。');
      setDeleteOpen(false);
    } catch (error: any) {
      setError(error.message || String(error));
    } finally {
      setBusy(false);
    }
  }

  async function inspect() {
    setInspectionBusy(true); setError('');
    try {
      const query = new URLSearchParams({limit: '100'});
      if (tick) { query.set('start', tick); query.set('end', String(Number(tick) + 5)); }
      setInspection(await api('/jobs/' + active + '/inspect/' + table + '?' + query.toString()));
    } catch (error: any) {
      setError(error.message || String(error));
    } finally {
      setInspectionBusy(false);
    }
  }

  const counts = jobs.reduce<Record<string, number>>((acc, item) => { acc[item.status] = (acc[item.status] || 0) + 1; return acc; }, {});

  return (
    <div className="jobs-page">
      <div className="page-toolbar">
        <Segmented label="任务与数据分区" value={section} onChange={setSection} options={[
          {value: 'queue', label: '任务队列'},
          {value: 'aggregate', label: '多场汇总'},
          {value: 'storage', label: '本地存储'},
          {value: 'inspector', label: '数据检查'},
        ]} />
      </div>
      {error && <Callout tone="danger" title="操作失败" action={<button type="button" onClick={() => setError('')}>关闭</button>}>{error}</Callout>}
      {message && <Callout tone="ok" action={<button type="button" onClick={() => setMessage('')}>关闭</button>}>{message}</Callout>}

      {section === 'queue' && (
        <>
          <div className="queue-summary">
            {['running', 'queued', 'partial', 'succeeded', 'failed', 'cancelled'].filter(status => counts[status]).map(status => (
              <div key={status}><span>{statusText(status)}</span><strong>{counts[status]}</strong></div>
            ))}
            {!jobs.length && <p className="muted">还没有任务。回到概览上传一场 demo。</p>}
          </div>
          <section className="panel queue-panel">
            <div className="section-head">
              <div><h2>独立文件队列</h2><p>同内容 demo 只解析一次；失败按任务隔离，不会停止其它文件。</p></div>
              <div className="section-actions">
                <button type="button" disabled={!chosenJobs.length} onClick={() => setChosenJobs([])}>清空选择</button>
                <button type="button" className="primary" disabled={!chosenJobs.length || busy} onClick={() => { setSection('aggregate'); aggregateSelected(); }}>
                  汇总所选（{chosenJobs.length}）
                </button>
              </div>
            </div>
            <div className="table-scroll">
              <table className="queue-table">
                <thead>
                  <tr><th>选择</th><th>文件 / 地图</th><th>状态</th><th>阶段 / 说明</th><th>更新时间</th><th>操作</th></tr>
                </thead>
                <tbody>
                  {ordered.map(item => {
                    const terminal = ['succeeded', 'partial'].includes(item.status);
                    const running = ['queued', 'running'].includes(item.status);
                    return (
                      <tr key={item.id} className={item.id === active ? 'active-row' : ''}>
                        <td><input type="checkbox" aria-label={'选择 ' + item.filename} disabled={!terminal} checked={chosenJobs.includes(item.id)} onChange={event => setChosenJobs(event.target.checked ? [...chosenJobs, item.id] : chosenJobs.filter(id => id !== item.id))} /></td>
                        <td>
                          <strong className="queue-file">{item.filename}</strong>
                          <small>{item.map_name || '地图未知'} · {item.id.slice(0, 8)}</small>
                        </td>
                        <td><Badge status={item.status} /></td>
                        <td className="queue-stage">
                          <span>{item.stage || '—'}</span>
                          {item.detail && <small>{String(item.detail).split('\n')[0]}</small>}
                          {item.error && <details><summary>查看错误</summary><p className="danger-text">{item.error}</p></details>}
                        </td>
                        <td className="num queue-time">{formatDate(item.updated)}</td>
                        <td>
                          <div className="row-actions">
                            {terminal && <button type="button" onClick={() => onOpenAnalysis(item.id)}>查看</button>}
                            {running && <button type="button" onClick={() => onCancel(item.id)}>取消</button>}
                            {!running && <button type="button" onClick={() => onRetry(item.id)}>重试</button>}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {section === 'aggregate' && (
        <section className="panel">
          <div className="section-head">
            <div><h2>多场汇总</h2><p>只合并相同模块、指标、范围、参数和算法版本的比率与计数；中位数和分位数不平均。</p></div>
            <button type="button" className="primary" disabled={!chosenJobs.length || busy} onClick={aggregateSelected}>{busy ? '正在汇总…' : '汇总所选任务'}</button>
          </div>
          <div className="chosen-list">
            {chosenJobs.length ? chosenJobs.map(id => {
              const item = jobs.find(job => job.id === id);
              return <span className="chip" key={id}>{item?.filename || id}<button type="button" aria-label="移除" onClick={() => setChosenJobs(chosenJobs.filter(value => value !== id))}>×</button></span>;
            }) : <p className="muted">先在「任务队列」勾选已完成的任务。相同 demo 哈希只会计入一次。</p>}
          </div>
          {aggregate ? (
            <>
              <div className="aggregate-head"><strong>{aggregate.distinct_demos} 个不同 demo</strong><span>{aggregate.metrics?.length || 0} 组可比指标{chosenJobs.length > aggregate.distinct_demos ? ' · 所选任务中有 ' + (chosenJobs.length - aggregate.distinct_demos) + ' 个重复内容，只计一次' : ''}</span></div>
              <div className="table-scroll">
                <table>
                  <thead><tr><th>模块 / 指标</th><th>范围</th><th>合并值</th><th>场数</th><th>覆盖率</th><th>质量</th></tr></thead>
                  <tbody>
                    {(aggregate.metrics || []).map((metric: Metric, index: number) => {
                      const display = metricDisplay(metric);
                      return (
                        <tr key={index}>
                          <td><strong>{metricName(metric.metric_id)}</strong>{technicalDetails && <small>{MODULE_TITLES[metric.module_id || ''] || metric.module_id} · {metric.metric_id}</small>}</td>
                          <td className="scope-cell">{[metric.scope?.player_id ? '玩家 ' + (result?.players.find((person: Obj) => person.player_id === metric.scope.player_id)?.name || metric.scope.player_id) : '全部玩家', ...Object.entries(metric.scope || {}).filter(([key]) => key !== 'player_id').map(([key, value]) => (SCOPE_NAMES[key] || key) + '：' + String(value))].join(' · ')}</td>
                          <td className="num">{display.text}{display.suffix}{metric.value === null && <small>{display.unavailable}</small>}</td>
                          <td className="num">{metric.demo_count ?? '—'}</td>
                          <td>{metric.coverage === 1 && !fullCoverage ? '—' : coverageText(metric.coverage)}</td>
                          <td><span className={'pill ' + (metric.value === null || metric.quality === 'unknown' ? 'warn' : 'neutral')}>{metric.value === null ? '有场次不可用' : '可合并'}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="muted">{(aggregate.limitations || []).join(' ')}</p>
            </>
          ) : <EmptyState icon="stack" title="还没有汇总结果"><p>选择至少两个已完成任务后点击汇总。单场也可以汇总，但不会有跨场趋势的意义。</p></EmptyState>}
        </section>
      )}

      {section === 'storage' && (
        <section className="panel">
          <div className="section-head"><div><h2>本地文件与缓存</h2><p>删除应用内原始副本后，已生成的事实和结果仍保留，但无法补抽缺失字段。</p></div><button type="button" onClick={() => api('/storage').then(setStorage).catch(error => setError(error.message))}>刷新</button></div>
          {!storage && <Spinner label="正在读取存储占用…" />}
          {storage && (
            <>
              <div className="storage-grid">
                {Object.entries(storage.groups || {}).map(([name, size]) => (
                  <div className="storage-card" key={name}>
                    <span>{({uploads: '原始 demo 副本', facts: '高频事实', module_cache: '模块缓存', results: '分析结果'})[name] || name}</span>
                    <strong>{formatBytes(size)}</strong>
                  </div>
                ))}
              </div>
              <p className="storage-policy">{storage.policy}</p>
              <p className="muted">数据目录：<code>{storage.root}</code></p>
              {result && <button type="button" className="danger" onClick={() => setDeleteOpen(true)}>清理当前 demo 的应用内副本</button>}
              <Modal open={deleteOpen} onClose={() => setDeleteOpen(false)} title="清理应用内原始副本？" eyebrow="DELETE UPLOAD" size="sm" label="确认清理"
                footer={<><button type="button" onClick={() => setDeleteOpen(false)}>取消</button><button type="button" className="danger" disabled={busy} onClick={removeCopy}>确认清理</button></>}>
                <p>只删除应用保存的这份原始 demo。已生成的事实、结果、个人存档与外部原始文件不受影响。</p>
                <p className="muted">清理后仍可查看已有结果，但重新分析需要重新提供原始文件。</p>
              </Modal>
            </>
          )}
        </section>
      )}

      {section === 'inspector' && (
        <section className="panel">
          <div className="section-head"><div><h2>开发者数据检查</h2><p>这里直接读取事实表与字段目录，用来排查解析问题；普通复盘不需要打开。</p></div><span className="pill warn">技术工具</span></div>
          <Callout tone="warn" title="这些不是面向普通用户的结论">
            原始字段、命令偏移和事件序号用于验证数据来源。不要把这里的 JSON 当成额外指标；字段缺失不代表数值为 0。
          </Callout>
          <div className="inspector-controls">
            <Field label="数据表">
              <select value={table} onChange={event => { setTable(event.target.value); setInspection(null); }}>{TABLES.map(item => <option key={item}>{item}</option>)}</select>
            </Field>
            <Field label="起始时间步（可选）">
              <input type="number" value={tick} placeholder="例如 1272" onChange={event => setTick(event.target.value)} />
            </Field>
            <button type="button" disabled={!result || inspectionBusy} onClick={inspect}>{inspectionBusy ? '读取中…' : '读取最多 100 条'}</button>
          </div>
          {!result && <p className="muted">先选择一个已完成的任务。</p>}
          {inspection && <pre className="inspector-json">{JSON.stringify(inspection, null, 2)}</pre>}
          {!inspection && result && <p className="muted">选择表并读取。commands 表有真实字节偏移；事件表只有类型内序号，不虚构跨类型顺序。</p>}
        </section>
      )}
    </div>
  );
}
