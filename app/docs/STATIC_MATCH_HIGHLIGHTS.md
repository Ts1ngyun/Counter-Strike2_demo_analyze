# Static appearance and match highlights

Updated 2026-10-28. Basic stats module: **1.3.0**. This supersedes earlier liquid-glass and Impact notes.

## Using the interface

Open 比赛分析 → 基础比赛统计 and select a player. Below the performance summary, 对局细看 has two views:

- **对位**: enemy kills, deaths to each enemy, and their difference. Expand an opponent to jump to individual events in the 2D replay.
- **多杀与残局**: exact 2 / 3 / 4 / 5+ kill rounds and 1v1–1v5 attempts. Round buttons open the replay at the first kill or the start of the last-alive situation.

The section follows the selected player, the single-round statistics mode, and the T/CT filter. It always uses all weapons, as stated in its subtitle. In match mode, the existing evidence-only round filter does not change this section. Old reports need reanalysis to generate these details.

## Counting rules

- Only complete official scoring rounds enter analysis. Warmup, knife rounds and restarts that do not count toward the score follow the existing round classifier and are excluded. A scoring round with only knife kills remains eligible.
- Opponent rows use enemy `player_death` events whose attacker/victim identities and team fields match the round roster. Suicide, team kills and world deaths do not earn opponent kills or multi-kills. Zero-interaction opponents still appear from the per-round roster.
- A three-kill round is counted once under three kills, never also under two kills.
- A clutch attempt starts when a team has exactly one player alive and at least one opponent alive. The opponent count at that moment defines its 1vN category; later deaths do not reclassify it. Each side can have at most one attempt per round. Both sides may have a 1v1 attempt.
- **Success means the player's team wins the round**, including a posthumous bomb explosion win. Saving in a lost round is a failed attempt under this definition. This is a local documented rule, not a claim to match a third-party website's clutch statistics.
- Deaths at the same tick are applied together; no sub-tick ordering is invented. A final kill that leaves zero opponents cannot start a new attempt.
- Dead grenade throwers can still receive kills. Team/world deaths update alive counts without awarding enemy-kill credit.
- Clutches require a complete alive 5v5 starting roster, consistent death/team records, and matching end-of-round alive states. If those checks fail, the whole round is excluded from clutch counting and appears in the data-incomplete disclosure. No attempts is distinct from no usable data. Missing winner produces `outcome: unknown`.

## Data contract

No new endpoint is required. `GET /api/jobs/{job_id}/result` and the complete JSON export include:

```text
modules.basic_stats.details.highlights
  schema_version: 1
  duels[]: round_id, tick, attacker_id, victim_id, weapon, headshot, event_id
  multi_kills[]: round_id, player_id, kills, tick, event_refs[]
  clutches[]: round_id, player_id, team, opponents, opponent_ids[], tick,
             end_tick, outcome (won/lost/unknown), survived, event_refs[]
  clutch_rounds[]: round_id, known, reason (null or a short explanation)
```

Player IDs remain strings. `team` is 2 for T, 3 for CT. `event_refs` refer to normalized event IDs, not module evidence IDs. Round labels use the round's cumulative official score; replay uses stable `round_id` and tick. The details are not additional MetricResult rows, so the metric-only CSV does not contain them. The interactive interface and full JSON provide the new breakdowns.

Implementation: `backend/modules/basic_stats/highlights.py`, integration in `analyzer.py`, UI in `frontend/src/views/MatchHighlights.tsx` and `match-highlights.css`.

## Static appearance

The liquid-glass toggle is removed. All themes use static gradients, borders and highlights; no live refraction or backdrop sampling. CSS backdrop filters are disabled, including overlays. The page background has no CSS blur or continuous drift animation. Short hover/entrance effects remain governed by the motion preference.

For uploaded backgrounds, `Background.tsx` retains the original image and a rendered WebP in browser IndexedDB. Upload and 保存静态背景 perform one Canvas render; the displayed background then uses those saved pixels. The softness slider is a draft until saved. Opacity changes reuse the rendered image. Existing backgrounds are migrated once. Files stay local to the browser and are not sent to the backend. Backgrounds are limited to 12 MB / 40 MP, with rendered output capped at a 2560-pixel longest edge. This imitates a frosted appearance; it does not capture or continuously blur the page behind each panel.

## Retired metric

Impact is no longer calculated or displayed. Historical report responses and exports filter it without rewriting stored result files. Original archived snapshots remain historical records. KAST is unchanged. No Rating formula was added; Round Swing remains the existing experimental preplant estimate.

## Verification

- Backend suite: 185 passed. New tests cover exact multi-kills, 1vN transitions, simultaneous deaths, terminal kills, posthumous bomb wins, dead throwers, incomplete states and non-mutating historical Impact projection.
- TypeScript and Vite production build passed.
- Real demo `2398717_8244_2.dem`, de_anubis, job `6cf1fd30788b409c90ca281c92fe4651`: 20 official rounds, 130 opposing kills, 33 player-round multi-kill entries, 22 last-alive attempts. All 20 rounds pass clutch-state checks. Each of the ten opponent-kill totals matches the corresponding base kill metric.
- m0NESY: three two-kill rounds (9, 18, 20); two 1v1 attempts, one win (round 9). The win button opens the relevant round's 2D replay.
- Browser check: no computed backdrop filters; background filter and continuous animation are `none`. Uploaded background softness saves and survives reload, then the test background was removed.

Screenshots: `ui-redesign-highlights.png`, `ui-redesign-matchups.png`.

- Responsive checks: 1440-pixel desktop uses four multi-kill columns; 390-pixel mobile uses two, with no page-level horizontal overflow. Light and dark themes checked. Round 9 filtering shows one two-kill round and one successful 1v1; returning to match mode restores the full totals.
- All player multi-kill distributions match the existing per-round kill histogram. Historical result API contains no Impact metric.
