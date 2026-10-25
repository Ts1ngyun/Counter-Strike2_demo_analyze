# CS2 Demo Evidence Lab

**An offline workspace for Counter-Strike 2 demo analysis and match review.**

English · [简体中文](README.zh-CN.md)

Turn recorded matches into player statistics, reviewable combat clips, flashbang records, and a 2D tactical replay. Every analysis keeps its supporting evidence and distinguishes observed facts, estimates, and unavailable data.

Built with **Python / FastAPI** and **React / TypeScript / Vite**. Analysis runs locally after the initial dependency setup; no cloud account is required to use the application. The current application interface is primarily in Chinese.

## Features

| Feature | What you can review |
| --- | --- |
| Match statistics | Player and round statistics, damage, opening duels, and recorded assists. |
| Combat and death review | Event timelines, nearby player states, review tags, and your own notes and conclusions. |
| Aim movement | Vertical aim changes before kills, before deaths, and before the first shot in non-kill engagement sequences. |
| Movement and shooting | Movement-to-first-shot readiness and low-speed shooting, with selectable weapon groups and per-shot evidence. |
| Sustained fire | Sampled aim trajectories, attack-input observations, and shot-to-damage-event associations. |
| Flashbang analysis | Recorded enemy, teammate, and self effects, game-recorded flash assists, and links to replay. |
| 2D tactical replay | Offline radar maps, player positions and facing directions, event navigation, bookmarks, notes, and drawings. |
| Personal archives | Multiple SteamIDs in one archive, separate player trends, duplicate-match handling, and historical snapshots. |

Light, dark, and system themes are available, with compact and comfortable layouts. Full-coverage labels and technical details are hidden by default to keep the interface readable.

## Quick start

The included launch scripts target **Windows**.

**Requirements:** Python 3.12 (64-bit) and Node.js 24, available on your PATH.

1. Download or clone the repository.
2. Run `app/setup.cmd` to install dependencies and build the frontend. This initial step requires an internet connection.
3. Run `app/start.cmd` and open [http://127.0.0.1:8765](http://127.0.0.1:8765).
4. Import a `.dem` file and choose a completed analysis to explore.
5. Run `app/stop.cmd` when you want to stop the local service.

This is a source distribution, not a standalone executable. Once dependencies are installed, demo analysis and the bundled radar maps work offline.

## Review workflow

Start with a player's statistics, then inspect a combat clip or flashbang record. Jump to the corresponding replay tick to review positions and events, and save notes or bookmarks for later.

To track a player over time, create an archive, select one or more SteamIDs from the current match, and save them to that archive. Each ID retains its own metrics. Saving the same match again does not double-count it; changed analysis results retain earlier snapshots.

## Data and limitations

- **Evidence comes first.** Missing observations remain unknown rather than becoming zeroes. Estimates and incomplete coverage are explicitly labeled.
- **Flash effects depend on available events.** When native blind events are absent, supported state changes may provide estimated records, not a complete reconstruction of what each player saw.
- **Aim movement is descriptive.** A smaller vertical angle range does not prove correct crosshair placement. Aim trajectories are not bullet impacts, and the application does not invent a recoil-accuracy score.
- **Radar maps are a visual reference.** Asset and demo versions may differ. The replay does not reconstruct exact visibility, smoke occlusion, or client-side rendering.
- **Role and positioning analysis remain planned.** Their interfaces exist, but these modules are disabled.

Imported files, cached analysis, and personal archives are stored under `app/data/`. They are excluded from the repository. To back up local records, stop the application before copying this directory. Saved snapshots remain readable without the original task, while replay still requires the corresponding parsed facts.

## Development

Run backend tests from the repository root after setup:

```powershell
app/.venv/Scripts/python.exe -X utf8 -m pytest app/tests -q
```

Build the frontend:

```powershell
npm.cmd run build --prefix app/frontend
```

The backend, frontend, tests, and module template are under `app/backend/`, `app/frontend/`, `app/tests/`, and `app/module_template/` respectively.

## Documentation

The detailed technical documentation is currently in Chinese.

- [User guide](app/docs/README.md)
- [Algorithms and limitations](app/docs/ALGORITHMS.md)
- [Data and timing contracts](app/docs/CONTRACTS.md)
- [Replay behavior](app/docs/REPLAY.md)
- [Combat and aim review](app/docs/COMBAT_REVIEW.md)
- [Archives and validation notes](app/docs/REVIEW_V3.md)
- [Module extension guide](app/docs/EXTENDING.md)

## Third-party assets

Bundled radar maps originate from Awpy-data / Valve. See the [map asset notice](app/frontend/public/maps/NOTICE.txt) for sources and copyright information. Third-party dependencies retain their respective licenses.
