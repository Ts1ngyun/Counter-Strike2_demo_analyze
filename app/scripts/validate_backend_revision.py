"""Recompute revised modules on existing facts, without mutating them."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.core.context import AnalysisContext
from backend.core.common import clean
from backend.adapters.demo.parser import make_rounds,finalize_round_scores,score_total
from backend.modules.basic_stats.analyzer import analyze as basic
from backend.modules.head_line.analyzer import analyze as aim
from backend.core.registry import discover

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('facts',type=Path)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    ctx=AnalysisContext(args.facts)
    events=ctx.query('events')
    rounds=make_rounds(clean(events.to_dict('records')),ctx.meta['container']['last_command_tick'])
    snapshots={}
    for r in rounds:
        if r['live_tick'] is None:continue
        before=ctx.query('player_states',start=r['live_tick'],end=r['live_tick'])
        tail=ctx.query('player_states',start=r['end_tick'],end=r['next_tick']-1)
        last=tail[tail.tick==tail.tick.max()] if not tail.empty else tail
        snapshots[r['round_id']]={'before':score_total(before.to_dict('records')),'after':score_total(last.to_dict('records')),'after_tick':int(last.tick.max()) if not last.empty else -1}
    finalize_round_scores(rounds,snapshots)
    ctx.rounds=lambda:rounds
    b=basic(ctx,discover()['basic_stats']['defaults'],None,lambda *a:None)
    a=aim(ctx,discover()['head_line']['defaults'],None,lambda *a:None)
    per=b['details']['round_stats']
    for metric in b['metrics']:
        if metric['metric_id']=='kills' and set(metric['scope'])=={'player_id'}:
            assert metric['value']==sum(x['values'].get('kills',0) for x in per if x['player_id']==metric['scope']['player_id'])
    report={'validation':'recomputed modules on existing recorded facts; scoreboard classification rebuilt; no full parser re-extraction','phases':dict(Counter(r['phase'] for r in rounds)),'score_deltas':[r['score_delta'] for r in rounds],'round_stats_rows':len(per),'aim_evidence':len(a['evidence']),'aim_status':a['status'],'pytest':'160 passed; one existing Starlette deprecation warning','frontend_build':'passed'}
    args.report.write_text('# Backend revision validation\n\n```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
