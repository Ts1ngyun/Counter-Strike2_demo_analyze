import {useBackgroundLayer} from '../theme/Background';
import React, {useEffect, useMemo, useState} from 'react';
import {AppearancePanel, ParamsDialog, Sidebar, TopBar, type Tab} from './chrome';
import {useAppearance, PALETTES} from '../theme/appearance';
import {api, ApiError, uploadDemo} from './api';
import {Badge, Callout, EmptyState, Spinner} from '../ui/primitives';
import Icon from '../ui/Icon';
import Overview from '../views/Overview';
import Analysis from '../views/Analysis';
import Jobs from '../views/Jobs';
import {Replay} from '../Replay';
import Profiles from '../Profiles';
import type {Job, Obj, Result} from './format';
import '../styles/app.css';

type ScopeMode = 'match' | 'round';
type ReplayFocus = {tick: number; round_id?: string; player_id?: string; nonce: number; jobId: string};

function query(name: string): string {
  try { return new URLSearchParams(window.location.search).get(name) || ''; } catch { return ''; }
}
function initialTab(): Tab {
  const value = query('view');
  return value === 'analysis' || value === 'replay' || value === 'profiles' || value === 'jobs' ? value : 'overview';
}

export default function App() {
  useBackgroundLayer();
  const appearance = useAppearance();
  const {prefs} = appearance;
  const [tab, setTab] = useState<Tab>(initialTab);
  const [modules, setModules] = useState<Obj[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [autoPicked, setAutoPicked] = useState(false);
  const [active, setActive] = useState(() => query('job'));
  const [result, setResult] = useState<Result | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [moduleId, setModuleId] = useState(() => query('module') || 'basic_stats');
  const [player, setPlayer] = useState(() => query('player'));
  const [round, setRound] = useState(() => query('round'));
  const [scopeMode, setScopeMode] = useState<ScopeMode>(() => query('scope') === 'round' ? 'round' : 'match');
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [params, setParams] = useState<Obj>({});
  const [steamIds, setSteamIds] = useState('');
  const [showParams, setShowParams] = useState(false);
  const [showAppearance, setShowAppearance] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [replayFocus, setReplayFocus] = useState<ReplayFocus | undefined>();
  const [mapFilter, setMapFilter] = useState('');
  const [chosenJobs, setChosenJobs] = useState<string[]>([]);
  const [aggregate, setAggregate] = useState<Obj | null>(null);

  const job = jobs.find(item => item.id === active);
  const terminal = Boolean(job && ['partial', 'succeeded'].includes(job.status));
  const running = Boolean(job && ['queued', 'running'].includes(job.status));
  const mapNames = Array.from(new Set<string>(jobs.map(item => item.map_name).filter((name): name is string => Boolean(name))));
  const visibleJobs = mapFilter ? jobs.filter(item => item.map_name === mapFilter) : jobs;
  const manifest = modules.find(item => item.id === moduleId);
  const paletteName = prefs.palette === 'custom' ? '自定义配色' : (PALETTES.find(item => item.id === prefs.palette)?.name || '橙白');

  function catchError(input: any) {
    if (input instanceof ApiError) setError(input.message);
    else setError(input?.message || String(input));
  }

  useEffect(() => {
    let cancelled = false;
    api('/modules').then(list => {
      if (cancelled) return;
      setModules(list);
      setSelectedModules(previous => previous.length ? previous : list.filter((item: Obj) => item.enabled).map((item: Obj) => item.id));
      setParams(previous => Object.keys(previous).length ? previous : Object.fromEntries(list.map((item: Obj) => [item.id, item.defaults])));
    }).catch(catchError);

    const load = () => api('/jobs').then(list => {
      if (cancelled) return;
      setJobs(list);
      setJobsLoaded(true);
    }).catch(catchError);
    load();
    const timer = window.setInterval(load, 3000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (autoPicked || !jobsLoaded) return;
    if (active) { setAutoPicked(true); return; }
    const candidate = jobs.find(item => ['partial', 'succeeded'].includes(item.status));
    if (candidate) { setAutoPicked(true); setActive(candidate.id); }
  }, [autoPicked, jobsLoaded, jobs, active]);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setResultLoading(false);
    if (!active || !terminal) return;
    setResultLoading(true);
    api('/jobs/' + active + '/result').then(data => {
      if (cancelled) return;
      setResult(data);
      setParams(previous => ({...previous, ...(data.config?.parameters || {})}));
      const configured = data.config?.modules || [];
      const missing = modules.filter(item => item.enabled && !data.modules?.[item.id]).map(item => item.id);
      setSelectedModules(Array.from(new Set<string>([...configured, ...missing])));
      setResultLoading(false);
    }).catch(input => {
      if (cancelled) return;
      setResultLoading(false);
      catchError(input);
    });
    return () => { cancelled = true; };
  }, [active, terminal, modules]);

  useEffect(() => {
    if (!result) return;
    if (player && !result.players.some(person => person.player_id === player)) setPlayer('');
    if (round && !result.rounds.some(item => item.round_id === round)) setRound('');
  }, [result, player, round]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(''), 6500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    for (const key of ['job', 'view', 'module', 'player', 'round', 'scope']) parameters.delete(key);
    if (active) parameters.set('job', active);
    if (tab !== 'overview') parameters.set('view', tab);
    if (tab === 'analysis') {
      parameters.set('module', moduleId);
      if (player) parameters.set('player', player);
      if (round) parameters.set('round', round);
      if (scopeMode === 'round') parameters.set('scope', 'round');
    }
    const search = parameters.toString();
    window.history.replaceState(null, '', window.location.pathname + (search ? '?' + search : ''));
  }, [active, tab, moduleId, player, round, scopeMode]);

  function config() {
    return {
      modules: selectedModules,
      parameters: params,
      players: steamIds.split(/[\s,，]+/).filter(Boolean),
    };
  }

  function changeMap(value: string) {
    setMapFilter(value);
    const candidates = value ? jobs.filter(item => item.map_name === value) : jobs;
    if (active && !candidates.some(item => item.id === active)) {
      const next = candidates.find(item => ['partial', 'succeeded'].includes(item.status));
      setActive(next?.id || '');
    }
  }

  async function upload(files: FileList | File[]) {
    if (!selectedModules.length) { setError('模块定义还在加载，请稍等一秒再选择文件。'); return; }
    setMapFilter('');
    setError(''); setNotice(''); setUploading(true); setUploadProgress(0);
    try {
      for (const file of Array.from(files)) {
        setNotice('正在上传 ' + file.name + '…');
        const created = await uploadDemo(file, config(), fraction => setUploadProgress(fraction));
        if (created?.id) setActive(created.id);
        setNotice(created?.duplicate ? '检测到相同内容，复用本地副本。任务已入队。' : '文件已入队，正在本机分析。');
      }
      setJobs(await api('/jobs'));
    } catch (input) {
      catchError(input);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  }

  async function cancelJob(id = active) {
    try {
      await api('/jobs/' + id + '/cancel', {method: 'POST'});
      setNotice('已请求取消任务。已完成的模块结果可能仍会保留。');
      setJobs(await api('/jobs'));
    } catch (input) { catchError(input); }
  }

  async function retryJob(id = active, changed = false) {
    try {
      const created = await api('/jobs/' + id + '/retry', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: changed ? JSON.stringify(config()) : 'null',
      });
      setActive(created.id);
      setShowParams(false);
      setScopeMode('match');
      setNotice('已创建重算任务；满足版本与字段条件的事实与模块缓存会复用。');
      setJobs(await api('/jobs'));
      setTab('analysis');
    } catch (input) { catchError(input); }
  }

  function toggleModule(id: string, enabled: boolean) {
    setSelectedModules(previous => enabled ? Array.from(new Set([...previous, id])) : previous.filter(item => item !== id));
  }

  function openAnalysis(options?: {player?: string; round?: string; scope?: ScopeMode; module?: string}) {
    if (options?.module) setModuleId(options.module);
    if (options?.player) setPlayer(options.player);
    if (options?.round) {
      setRound(options.round);
      setScopeMode(options.scope || 'round');
    } else if (options?.scope) {
      setScopeMode(options.scope);
    }
    setTab('analysis');
    window.scrollTo({top: 0, behavior: 'auto'});
  }

  function selectModule(id: string) {
    setModuleId(id);
    if (!['basic_stats', 'combat_review', 'utility_analysis'].includes(id)) setScopeMode('match');
  }

  function openReplay(focus: {tick: number; round_id?: string; player_id?: string}, jobId = active) {
    if (jobId !== active) setActive(jobId);
    setReplayFocus({...focus, jobId, nonce: Date.now()});
    if (focus.player_id) setPlayer(focus.player_id);
    setTab('replay');
  }

  const topbarActions = (
    <>
      {mapNames.length > 1 && (
        <label className="map-control">
          <span>地图</span>
          <select value={mapFilter} onChange={event => changeMap(event.target.value)} aria-label="按地图筛选任务">
            <option value="">全部地图</option>
            {mapNames.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      )}
      <label className="match-control">
        <span>当前比赛</span>
        <select value={active} onChange={event => setActive(event.target.value)} aria-label="选择比赛任务">
          <option value="">选择任务</option>
          {[...visibleJobs].sort((a, b) => (b.created || 0) - (a.created || 0)).map(item => (
            <option key={item.id} value={item.id}>{item.filename + ' · ' + (item.map_name || '地图未知')}</option>
          ))}
        </select>
      </label>
      {job && <Badge status={job.status} />}
      <button type="button" onClick={() => setShowParams(true)}><Icon name="sliders" size={15} />分析配置</button>
      {result && (
        <select className="export-select" aria-label="导出报告" defaultValue="" onChange={event => {
          if (event.target.value) window.open('/api/jobs/' + active + '/export/' + event.target.value, '_blank');
          event.target.value = '';
        }}>
          <option value="">导出报告</option>
          <option value="json">完整 JSON + 证据</option>
          <option value="csv">指标 CSV</option>
          <option value="html">离线 HTML 报告</option>
        </select>
      )}
      <button type="button" className="appearance-trigger" onClick={() => setShowAppearance(true)} aria-haspopup="dialog"><Icon name="glass" size={15} />主题</button>
    </>
  );

  const title = tab === 'analysis' ? '比赛分析' : tab === 'overview' ? '比赛概览' : tab === 'replay' ? '2D 战术回放' : tab === 'profiles' ? '个人存档' : '任务与数据';
  const eyebrow = tab === 'overview' ? 'CS2 / LOCAL EVIDENCE' : tab === 'analysis' ? 'ANALYSIS / EVIDENCE FIRST' : tab === 'replay' ? 'REPLAY / OBSERVED STATE' : tab === 'profiles' ? 'ARCHIVE / MULTI STEAMID' : 'JOBS / LOCAL STORAGE';

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">跳到主要内容</a>
      <Sidebar tab={tab} onSelect={setTab} moduleTitle={manifest?.title} paletteName={paletteName} onAppearance={() => setShowAppearance(true)} />
      <div className="app-body">
        <TopBar title={title} eyebrow={eyebrow}>{topbarActions}</TopBar>
        <main id="main" className="page">
          {error && <Callout tone="danger" title="操作没有完成" action={<button type="button" onClick={() => setError('')}>关闭</button>}>{error}</Callout>}
          {notice && <Callout tone="ok" action={<button type="button" onClick={() => setNotice('')}>关闭</button>}>{notice}</Callout>}

          {!result && running && (
            <section className="panel running-panel">
              <div className="running-head">
                <Spinner />
                <div><h2>{job?.status === 'queued' ? '任务排队中' : '正在从录像构建事实'}</h2><p>{job?.stage || '等待工作进程'}</p></div>
                <button type="button" onClick={() => cancelJob()}>取消任务</button>
              </div>
              {job?.detail && <pre className="running-detail">{String(job.detail)}</pre>}
              <p className="muted">分析在本机后台进行，可以切换页面；完成后结果会自动出现。原始文件解析可能需要几分钟。</p>
            </section>
          )}

          {!result && job && ['failed', 'cancelled'].includes(job.status) && (
            <section className="panel failed-panel">
              <div className="section-head"><div><h2>{job.status === 'failed' ? '这个文件分析失败' : '任务已取消'}</h2><p>{job.error || '任务没有产生结果。'}</p></div><button type="button" onClick={() => retryJob()}>重试 / 复用缓存</button></div>
              {job.detail && <details><summary>诊断细节</summary><pre>{job.detail}</pre></details>}
            </section>
          )}

          {resultLoading && <div className="page-loading"><Spinner label="正在载入分析结果…" /></div>}

          {tab === 'overview' && (
            <Overview
              result={result} jobs={visibleJobs} active={active} modules={modules}
              uploading={uploading} uploadProgress={uploadProgress}
              onUpload={upload} onSelectJob={setActive}
              onOpenAnalysis={openAnalysis}
              onOpenReplay={() => setTab('replay')}
              onOpenJobs={() => setTab('jobs')}
              onCancel={() => cancelJob()} onRetry={() => retryJob()}
              onOpenConfig={() => setShowParams(true)}
              technicalDetails={prefs.technicalDetails}
            />
          )}

          {tab === 'analysis' && (
            result && !resultLoading && modules.length ? (
              <Analysis
                key={active}
                result={result} job={job} active={active} modules={modules} manifest={manifest}
                moduleId={moduleId} onModule={selectModule}
                player={player} onPlayer={setPlayer}
                round={round} onRound={setRound}
                scopeMode={scopeMode} onScope={setScopeMode}
                prefs={prefs}
                onOpenConfig={() => setShowParams(true)}
                onReplay={openReplay}
                onRerun={() => retryJob(active, true)}
              />
            ) : (result && !modules.length ? (
              <div className="page-loading"><Spinner label="正在读取模块定义…" /></div>
            ) : (!resultLoading && !running && (
              <EmptyState icon="pulse" title={job ? '这个任务还没有结果' : '还没有选择比赛'} actions={<><button type="button" onClick={() => setTab('overview')}>回到概览</button><button type="button" onClick={() => setShowParams(true)}>分析配置</button></>}>
                <p>{job ? '任务需要先成功或部分完成，才能查看分析。' : '先在概览选择一场已完成任务，或上传新的 demo。'}</p>
              </EmptyState>
            )))
          )}

          {tab === 'replay' && (result ? (
            <Replay key={active} jobId={active} focus={replayFocus?.jobId === active ? replayFocus : undefined} onSelectPlayer={setPlayer} />
          ) : (
            <EmptyState icon="play" title="先选择一场已完成比赛" actions={<button type="button" onClick={() => setTab('overview')}>回到概览</button>}>
              <p>2D 回放读取真实位置与事件；没有结果时不会绘制模拟轨迹。</p>
            </EmptyState>
          ))}

          {tab === 'profiles' && (
            <Profiles showFullCoverage={prefs.fullCoverage} technicalDetails={prefs.technicalDetails} jobId={active} result={result} currentPlayer={player}
              onOpenJob={(id, playerId) => { setMapFilter(''); setActive(id); if (playerId) setPlayer(playerId); setTab('analysis'); }}
              onReplay={(jobId, focus) => openReplay(focus, jobId)} />
          )}

          {tab === 'jobs' && (
            <Jobs
              jobs={visibleJobs} active={active} result={result}
              onSelect={setActive}
              onCancel={cancelJob}
              onRetry={id => retryJob(id)}
              onOpenAnalysis={(id, playerId) => { setActive(id); if (playerId) setPlayer(playerId); setTab('analysis'); }}
              chosenJobs={chosenJobs} setChosenJobs={setChosenJobs}
              aggregate={aggregate} setAggregate={setAggregate}
              fullCoverage={prefs.fullCoverage} technicalDetails={prefs.technicalDetails}
            />
          )}

          <footer className="app-footer">
            <a href="/fonts/harmonyos/LICENSE.txt" target="_blank" rel="noreferrer">使用 HarmonyOS Sans 字体 · © Huawei · 字体许可</a>
            <span>CS2 Demo Lab · 本地分析</span>
            <span>离线复盘工具</span>
          </footer>
        </main>
      </div>

      <AppearancePanel open={showAppearance} prefs={prefs} resolvedTheme={appearance.resolvedTheme}
        onChange={appearance.setPrefs} onPreview={appearance.setPreview} onClose={() => setShowAppearance(false)} />

      <ParamsDialog open={showParams} onClose={() => setShowParams(false)} modules={modules}
        selectedModules={selectedModules} onToggle={toggleModule} params={params} onParams={setParams}
        activeJob={active} onApply={() => retryJob(active, true)} result={result}
        steamIds={steamIds} onSteamIds={setSteamIds} />

    </div>
  );
}
