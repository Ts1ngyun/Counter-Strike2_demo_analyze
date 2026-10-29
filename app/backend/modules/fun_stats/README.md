# Teammate flash statistics (fun_stats 1.0.2)

Four per-player metrics summarize native player_blind events: teammate effects, unique teammates, recorded blind seconds, and matched detonations affecting teammates. Only complete official rounds and live-round events are included. No damage or state-change inference is used.

Flash identity uses a unique same-tick, non-null entity ID and thrower match; otherwise the native round/tick/entity identity is retained. Effects are deduplicated by flash, thrower and target. Known zero-duration records are excluded. Missing duration does not erase a native blind event, but its duration remains unknown.

Native attacker_team_num takes priority; detonation team is the fallback. Conflicts are exposed in details.team_conflicts. utility_analysis 2.0.1 uses the same team precedence for native effects. The two modules still differ in scope: utility_analysis can show estimated state-change effects, while fun_stats requires native events.

Missing identity or team increases unknown_count. No confirmed effects with unresolved records yields null, not zero. Partial totals are known lower bounds. Missing throwers are never assigned effects; they conservatively reduce completeness for every player's effect, unique-target and duration metrics. Those unknown counts describe possible missing records, not additional confirmed teammates. Incident counts only cover matched detonations.

Per-target totals are available in details.per_teammate; all-missing durations are null. Evidence references point only to retained deduplicated effects. Generic cards and evidence views are supported; no custom fun dashboard is included.

## Validation

Run from app: python -m pytest tests -q.
Synthetic fixtures cover duplicates, missing fields, team conflicts, cancellation, evidence integrity and cross-module team precedence. The available Anubis fact tables lack native player_blind; they validate only the null/partial path. Positive real-demo validation remains outstanding. No demo or personal data is included.

Existing reports must be recomputed with fun_stats enabled. This is a module update, not an application release/version bump.
