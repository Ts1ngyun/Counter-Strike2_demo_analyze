import React, {useState} from 'react';
import type {Obj, Result} from '../app/format';
import './match-highlights.css';

type Props = {result: Result; player: string; roundId?: string; team?: string; onPlayer:(id:string)=>void;
  onReplay:(focus:{tick:number;round_id?:string;player_id?:string})=>void; onRerun:()=>void};

export default function MatchHighlights({result,player,roundId,team,onPlayer,onReplay,onRerun}:Props) {
  const [tab,setTab]=useState('duels');
  const details=result.modules.basic_stats?.details;
  const data=details?.highlights;
  const name=(id:string)=>result.players.find(p=>p.player_id===id)?.name || id;
  const roundName=(id:string)=>{const r=result.rounds.find(r=>r.round_id===id);return r?.score_after_total ? `第 ${r.score_after_total} 回合` : id;};
  const membership:Obj[]=details?.round_stats || [];
  const ownRounds=membership.filter(r=>r.player_id===player && (!roundId||r.round_id===roundId) && (!team||String(r.team)===team));
  const ids=new Set(ownRounds.map(r=>r.round_id));
  const inScope=(row:Obj)=>ids.has(row.round_id);
  const duels:Obj[]=(data?.duels||[]).filter(inScope).filter((d:Obj)=>d.attacker_id===player||d.victim_id===player);
  const enemies=new Set<string>();
  ownRounds.forEach(own=>membership.filter(r=>r.round_id===own.round_id&&r.team!==own.team&&[2,3].includes(r.team)).forEach(r=>enemies.add(r.player_id)));
  duels.forEach(d=>enemies.add(d.attacker_id===player?d.victim_id:d.attacker_id));
  const multi:Obj[]=(data?.multi_kills||[]).filter(inScope).filter((r:Obj)=>r.player_id===player);
  const clutches:Obj[]=(data?.clutches||[]).filter(inScope).filter((r:Obj)=>r.player_id===player);
  const unknown:Obj[]=(data?.clutch_rounds||[]).filter(inScope).filter((r:Obj)=>!r.known);
  const replay=(row:Obj)=>onReplay({tick:row.tick,round_id:row.round_id,player_id:player});
  return <section className="panel match-highlights" aria-label="对位、多杀与残局">
    <div className="section-head"><div><h2>对局细看</h2><p>{player?name(player)+' · ':''}{roundId?roundName(roundId):'全场'}{team?team==='2'?' · T 方':' · CT 方':''} · 全武器 · 仅正式计分回合</p></div>
      <div className="highlight-tabs" aria-label="对局细看内容">{[['duels','对位'],['highlights','多杀与残局']].map(([id,label])=><button key={id} aria-pressed={tab===id} onClick={()=>setTab(id)}>{label}</button>)}</div>
    </div>
    {!data ? <p>旧报告还没有这些明细。<button onClick={onRerun}>重新分析</button></p> : !player ? <label>选择玩家 <select value="" onChange={e=>onPlayer(e.target.value)}><option value="">请选择</option>{result.players.map(p=><option key={p.player_id} value={p.player_id}>{p.name||p.player_id}</option>)}</select></label> : !ownRounds.length ? <p className="muted">该范围没有这名玩家的正式回合记录。</p> : tab==='duels' ? <>
      <p className="highlight-help">与每位对手的击杀互换。展开可回看交手记录。</p>
      <div className="duel-head"><span>对手</span><span>击杀对方</span><span>被其击杀</span><span>净胜</span></div>
      {[...enemies].sort((a,b)=>name(a).localeCompare(name(b))).map(id=>{
        const rows=duels.filter(d=>d.attacker_id===id||d.victim_id===id),kills=rows.filter(d=>d.attacker_id===player).length,deaths=rows.length-kills,delta=kills-deaths;
        return <details className="duel-item" key={player+id+roundId+team}><summary><span>{name(id)}</span><strong>{kills}</strong><strong>{deaths}</strong><strong className={delta>0?'positive':delta<0?'negative':''}>{delta>0?'+':''}{delta}</strong></summary>
          <div className="highlight-chips">{rows.length?rows.map(d=><button key={d.event_id} onClick={()=>replay(d)} title="在 2D 回放中定位">{roundName(d.round_id)} · {d.attacker_id===player?'击杀':'阵亡'} · {d.weapon||'未知武器'} ↗</button>):<span className="muted">没有击杀互换</span>}</div>
        </details>;
      })}
    </> : <>
      <div className="highlight-subhead"><h3>多杀</h3><span className="highlight-help">单回合击杀数，互不重复计数。</span></div>
      <div className="multikill-grid">{[2,3,4,5].map(n=>{const rows=multi.filter(r=>n===5?r.kills>=5:r.kills===n);return <article key={n}><span>{n===5?'5+':n} 杀</span><strong>{rows.length}<small> 回合</small></strong><div className="highlight-chips">{rows.map(r=><button key={r.round_id} onClick={()=>replay(r)}>{roundName(r.round_id)} ↗</button>)}{!rows.length&&<small className="muted">暂无</small>}</div></article>;})}</div>
      <div className="highlight-subhead"><h3>残局</h3><details className="highlight-definition"><summary aria-label="残局统计说明">?</summary><p>只剩自己、对面仍有人时记为一次残局，按当时敌人数分类。最终队伍赢下回合就算成功，包括下包后阵亡但炸弹爆炸获胜。1v3 打到 1v1 只算一次 1v3；同一时间步的死亡一起处理。</p></details></div>
      {unknown.length>0&&<details className="highlight-unknown"><summary>{unknown.length} / {ownRounds.length} 回合的残局数据不完整，未计入</summary><ul>{unknown.map(r=><li key={r.round_id}>{roundName(r.round_id)}：{r.reason}</li>)}</ul></details>}
      <div className="table-scroll"><table className="clutch-table"><thead><tr><th>局面</th><th>成功 / 尝试</th><th>回合记录</th></tr></thead><tbody>{[1,2,3,4,5].map(n=>{const rows=clutches.filter(r=>r.opponents===n);return <tr key={n}><th>1v{n}</th><td>{unknown.length===ownRounds.length?'—':`${rows.filter(r=>r.outcome==='won').length} / ${rows.length}`}</td><td><div className="highlight-chips">{rows.map(r=><button className={r.outcome==='won'?'positive':''} key={r.round_id} onClick={()=>replay(r)}>{roundName(r.round_id)} · {r.outcome==='won'?'成功':r.outcome==='lost'?'失利':'胜负未知'} ↗</button>)}{!rows.length&&<span className="muted">{unknown.length===ownRounds.length?'数据不足':'暂无记录'}</span>}</div></td></tr>;})}</tbody></table></div>
    </>}
  </section>;
}
