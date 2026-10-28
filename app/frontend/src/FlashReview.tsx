import React, {useEffect, useMemo, useState} from 'react';
import './FlashReview.css';

type Obj = Record<string, any>;
type Props = {module: Obj; result: Obj; player: string; roundId?: string; onReplay: (location: {tick: number; round_id: string; player_id: string}) => void};
const relationNames: Record<string, string> = {enemy: '敌方', teammate: '队友', self: '自己', unknown: '关系未知'};
const qualityNames: Record<string, string> = {observed: '游戏事件', estimated: '状态推导', unknown: '影响未能完整判定'};
const duration = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)} 秒` : '未知';

export default function FlashReview({module, result, player, roundId, onReplay}: Props) {
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(0);
  const [showAssists, setShowAssists] = useState(false);
  const analyzedPlayers: string[] = result?.config?.players || [];
  const flashes: Obj[] = (module?.details?.flash_review || []).filter((f: Obj) => !analyzedPlayers.length || analyzedPlayers.includes(f.player_id));
  const assists: Obj[] = (module?.details?.flash_assists || []).filter((f: Obj) => !analyzedPlayers.length || analyzedPlayers.includes(f.player_id));
  const players: Obj[] = result?.players || [];
  const name = (id: string) => players.find(p => (p.player_id || p.steamid) === id)?.name || id || '未知玩家';
  const own = useMemo(() => flashes.filter(f => (!player || f.player_id === player) && (!roundId || f.round_id === roundId)), [flashes, player, roundId]);
  const ownAssists = assists.filter(f => (!player || f.player_id === player) && (!roundId || f.round_id === roundId));
  const visible = own.filter(f => filter === 'all' || filter === 'enemy' && f.enemy_count > 0 || filter === 'friendly' && (f.teammate_count > 0 || f.self_count > 0) || filter === 'unknown' && f.assessment !== 'observed' || filter === 'kills' && f.kills?.length > 0);
  useEffect(() => {setPage(0)}, [player, roundId, filter, module]);
  const replay = (item: Obj) => onReplay({tick: item.tick, round_id: item.round_id, player_id: item.player_id});
  if (!module?.details?.flash_review) return null;
  return <section className="panel flash-review" aria-label="逐颗闪光复盘">
    <div className="row"><div><h2>逐颗闪光复盘</h2><p className="muted">从每颗闪找到受影响的人，再回到对应交战。当前范围：{roundId || '全部回合'}。</p></div><span className="badge">{own.length} 次引爆</span></div>
    {!module.details.event_support?.native_blind_available && <p className="flash-caveat">这份录像缺少游戏直接记录的致盲事件。下面仅展示与唯一同时间步爆炸对应的新状态变化，标为“状态推导”。未检测到变化的闪仍为未知，不算零效果。</p>}
    {!module.details.event_support?.detonation_extracted && <p className="flash-caveat">当前分析尚未提取闪光引爆事件，请用新版模块重新分析。旧结果不会被解释成零颗闪。</p>}
    <div className="flash-summary">
      <span><strong>{own.filter(f => f.enemy_count > 0).length}</strong>已记录影响敌人</span>
      <span><strong>{own.filter(f => f.teammate_count > 0).length}</strong>已记录影响队友</span>
      <span><strong>{own.filter(f => f.self_count > 0).length}</strong>已记录影响自己</span>
      <span><strong>{own.filter(f => f.assessment !== 'observed').length}</strong>影响未完整判定</span>
    </div>
    <div className="flash-toolbar"><label>查看闪光<select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">全部引爆</option><option value="enemy">已记录影响敌人</option><option value="friendly">影响队友或自己</option><option value="kills">存在闪后击杀关联</option><option value="unknown">影响未完整判定</option></select></label><button aria-expanded={showAssists} onClick={() => setShowAssists(!showAssists)}>游戏记录闪助 · {ownAssists.length}</button></div>
    {showAssists && <div className="flash-assists"><p className="muted">游戏的 assistedflash 记录，独立于下方的状态推导；没有唯一证据时不归属到某一颗闪。</p>{ownAssists.length ? ownAssists.map(a => <div className="flash-assist-row" key={a.event_id}><span>{a.round_id} · {name(a.player_id)} 帮助 {a.killer_name || name(a.killer_id)} 击杀 {a.target_name || name(a.target_id)}</span><button onClick={() => replay(a)}>回放助攻</button></div>) : <p>当前筛选没有游戏记录闪光助攻。</p>}</div>}
    <div className="flash-list">{visible.slice(page * 12, page * 12 + 12).map(f => <article className="flash-card" key={f.evidence_id}>
      <div className="flash-card-heading"><div><strong>{f.player_name || name(f.player_id)}</strong><small>{f.round_id} · 时间步 {f.tick}</small></div><span className={`badge ${f.assessment === 'estimated' ? 'estimated' : f.assessment === 'unknown' ? 'unknown' : 'observed'}`}>{qualityNames[f.assessment]}</span><button onClick={() => replay(f)}>回放这颗闪</button></div>
      <div className="flash-effects">{f.effects.length ? f.effects.map((e: Obj, index: number) => <div key={`${e.target_id}:${index}`} className={`flash-effect flash-${e.relation}`}><span>{relationNames[e.relation]} · {e.target_name || name(e.target_id)}</span><strong>{duration(e.duration)}</strong><small>{e.source === 'player_blind' ? '事件记录时长' : '新记录的持续时间值'}</small></div>) : <p className="muted">{f.assessment === 'observed' ? '完整原生事件记录中未发现受影响玩家。' : '未能确认受影响玩家；这不表示该闪没有效果。'}</p>}</div>
      {f.kills?.length > 0 && <div className="flash-kills">{f.kills.map((k: Obj) => <p key={k.event_id}>闪后 {k.seconds_after.toFixed(2)} 秒，{k.killer_name || name(k.killer_id)} 击杀 {k.target_name || name(k.target_id)}{k.game_flash_assist_for_thrower ? ' · 该击杀有投掷者的游戏闪助记录' : ''}</p>)}<small>时间关联不证明因果，也不代表击杀时目标仍在致盲。</small></div>}
      <details><summary>查看判定依据</summary><p>{f.assessment_reason}</p><p>只比较爆炸所在时间步与上一个时间步。记录时长不代表屏幕全白时长，持续状态不逐帧累加。同一时间步的多颗闪和无法唯一配对的记录保留未知。</p></details>
    </article>)}</div>
    {!visible.length && <div className="empty">当前筛选没有闪光记录。</div>}
    {visible.length > 12 && <div className="flash-pagination"><span>{page * 12 + 1}–{Math.min(visible.length, (page + 1) * 12)} / {visible.length}</span><button disabled={page === 0} onClick={() => setPage(page - 1)}>上一页闪光</button><button disabled={(page + 1) * 12 >= visible.length} onClick={() => setPage(page + 1)}>下一页闪光</button></div>}
  </section>;
}
