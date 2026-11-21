# Store simulator

`apps/browser/scripts/sim/` runs the real browser store (`useBrowser`, with its persistence and the pinned-area sync
adapters) under plain node, on the same native fakes the store tests use, and drives it with seeded random sequences of
real actions. After every step it checks a set of rules; a failing sequence shrinks to the shortest one that still fails
the same rule, and prints it with a replay line.

```
pnpm -C apps/browser sim                                    the CI seed set
node apps/browser/scripts/sim/run.mjs --mode correctness --soak 60      keep drawing seeds for a minute
node apps/browser/scripts/sim/run.mjs --replay '[["shareTabs",0], …]'   replay one printed sequence step by step
node apps/browser/scripts/sim/run.mjs --src <dir>/apps/browser/src      drive an older commit's export (git archive)
```

The CI seed set is deterministic: the clock is fake, `Math.random` is seeded, timers of 20 ms or more never fire and
shorter ones run in order at the simulator's own turns, so the same tree prints the same output byte for byte.

## Actions

Open a tab (in the window's profile or another), close, select, move within a window and to another window, pin and
unpin (tile or row), group (pinned folder or plain group), ungroup, add to and take out of a group, new window, close
window, switch profile, create and delete a profile, share tabs across windows on or off, sleep, reopen a closed tab or
window, a sync patch (a second device pins or reorders, both devices sync, this one syncs twice), save then reload the
session, quit then relaunch. Each step carries four random picks that choose its targets from the live state, so a
shrunk sequence still means something after steps around it are removed.

## Rules

| Rule | Fails when |
| --- | --- |
| `pins` | a pin key of a profile (in a window, a pinned folder or parked) disappears in a step that didn't unpin it, take it out of a pinned folder, or delete its profile; pinning a tab leaves no pinned copy of it; unpinning or regrouping closes the tab and every copy of its page |
| `structure` | a tab isn't listed by exactly the window it names, an id in a window, group, selection, split or order list doesn't resolve, or a window's remembered active tab for a profile is missing or lives elsewhere |
| `session`, `relaunch` | save then reload, or quit then relaunch, changes the windows, tabs, pins and their placement, groups, parked pins, the recently closed lists or the sharing setting (both sides are copied before the save; tab order is compared within its section, the order `hydrate` restores, because the live store doesn't keep sections in order) |
| `sync` | the second sync with nothing new changes the pinned area, its folders, parked pins or each window's pin order |
| `reopen` | reopening leaves the entry it should restore on the list, or takes an entry off without opening or showing its pages |
| `errors` | anything is logged with `console.error` during a step (a settle that doesn't converge is logged, not thrown, outside tests) |
| reach | a CI run never reaches one of the actions, or one of the states the rules depend on (a sync that brought a change, a reload or relaunch holding pins, a window closed holding pins, a shared window closed into another, a reopen that restored something, a pin the person removed) |

## Known failures and regressions

`scripts/sim/known.json` holds shrunk sequences by issue. Those under `failing` reproduce a bug that is open today
and must still fail their rule; once a fix lands they pass and the run fails until the entry moves to `holding`, where
it must pass from then on. The CI run checks both lists.

## What it does not replace

It can stand in for hand-written store sequence tests.
It does not replace anything native, the timing gate, mount and render counts on a real build, looks checked from
pixels, the Linux and Windows adapters, or the conventions checks.
