# Persistent List Column Widths — Remember Resized Columns

Generic, reusable Odoo 19 module that makes manually-resized list (tree) view
column widths **persist** across navigation, view switches, and browser
sessions — per view, for every user, with no configuration required. Standard
Odoo 19 forgets a column's resized width the moment the list renderer unmounts;
this module remembers it and restores it the next time the view is shown.

Compatible with **Odoo 19 Community and Enterprise**. Depends only on `web`,
so it installs everywhere Odoo's web client runs — no Enterprise apps, no
accounting, no extra dependencies.

## Business problem

Users carefully drag a list view's columns to fit their data — widen a
description column, shrink a status column — and Odoo throws that work away the
moment the list renderer unmounts. That happens constantly:

- navigating to another menu and back,
- switching to kanban / form / pivot and returning to list,
- reloading the browser tab,
- opening an x2many embedded list inside a form and reopening it.

The widths are computed inside a hook and held only in a closure variable that
dies on unmount, so they are never persisted anywhere. Power users who live in
large list views lose their layout dozens of times a day.

This module makes those widths stick. The next time the same view is shown — in
the same session or after a full reload — the columns come back at the widths
the user left them, automatically.

## How it works

The entire column-width behavior in Odoo 19 lives in a single hook,
`useMagicColumnWidths` in
`web/static/src/views/list/column_width_hook.js`, consumed only by
`ListRenderer`. Computed widths live in a closure array that is discarded on
unmount, and any DOM width set from the outside is overwritten on the next
render when the hook re-applies its own frozen array — so an "overlay" approach
loses the race and flickers. The robust fix is to teach the hook itself to seed
from and save to storage:

1. **Vendored hook fork** — `static/src/persistent_column_width_hook.js` is a
   byte-for-byte copy of upstream `column_width_hook.js`, exporting
   `usePersistentColumnWidths`, with a handful of surgical edits (each tagged
   `// NOVALYFT`):
   - import the storage abstraction;
   - on the **first** width computation, seed `startingWidths` from storage
     (hash-gated), so restored widths flow through Odoo's own min/max + 100%-fit
     math and adapt cleanly to the current container width;
   - on **resize end**, save the final content-widths to storage;
   - expose a `resetView()` that clears storage and recomputes ideal widths;
   - always register the hook's effects (the native opt-in flag is neutered by
     the patch, below).
   The width math, freeze logic, and RTL delta handling are inherited
   unchanged.

2. **One prototype patch** — `static/src/list_renderer_patch.js` turns off the
   native `ListRenderer.useMagicColumnWidths` flag (so the stock hook registers
   no side effects) and swaps in `usePersistentColumnWidths` from `setup()`.
   Because every list view — including x2many embedded lists — renders through
   `ListRenderer`, a single patch covers them all. Existing resize wiring keeps
   working because the returned API names (`onStartResize`, `resizing`,
   `resetWidths`) are preserved.

3. **`createViewKey()` storage key** — widths are keyed off Odoo's own
   `createViewKey()` (model + view id + x2many sub-view path + sorted field
   set), the same identifier Odoo already uses for its optional-columns memory.
   The storage key is `column_widths,${createViewKey()}`. This makes persistence
   per view and x2many-aware for free, and the hook's column-set hash
   automatically invalidates stored widths when the arch's columns change.

4. **localStorage abstraction** — `static/src/width_store.js` is the only module
   that references `localStorage`, exposing `loadWidths(key)` /
   `saveWidths(key, payload)` / `clearWidths(key)`. Every access is wrapped in
   `try/catch`, so private/incognito mode and storage-quota errors degrade
   silently to stock behavior and never throw. A future server-sync backend can
   be dropped in behind these three functions without touching the renderer.

A per-view **Reset column widths** item is added to the optional-columns
dropdown via OWL template inheritance
(`static/src/list_renderer_patch.xml`); selecting it clears the stored entry
for the current view and recomputes ideal widths immediately. The dropdown is
also made reachable on views with no optional columns when a saved width exists,
so the reset is always available.

## Installation

1. Drop `list_column_widths_persist/` into an Odoo 19 addons path. On
   Odoo.sh, commit the folder at the repo root next to any other addon
   folders.
2. Restart Odoo with that addons path included:
   `./odoo-bin -d <db> --addons-path=...,/path/to/odoo-custom-addon -u all`
3. From the Apps screen, search for "Persistent List Column Widths" and
   install.

Dependencies: `web` only — shipped with every Odoo edition.

## Configuration

None — **zero config, always on for every user.** There is no setting to
enable, no group to grant, and no per-model setup. Once installed, every list
view in the database remembers its resized column widths automatically.

## Limitations

- **Per browser profile.** Widths are stored in `localStorage`, so they are
  scoped to the browser profile on a given machine — effectively per user, but
  they do **not sync across devices or browsers**. A server-sync backend is
  possible in a future version; the storage layer is already abstracted for it.
- **No admin defaults.** There is no admin-defined, org-wide default column
  width — each user shapes their own views.
- **No per-user toggle.** The behavior is always on; there is no per-user
  enable/disable switch.
- **Opted-out renderers.** A renderer subclass that explicitly sets
  `static useMagicColumnWidths = false` is out of scope (no standard Odoo
  renderer does this).

## Maintainer note — per-version re-sync

`static/src/persistent_column_width_hook.js` is a deliberate **vendored fork**
of `web`'s `column_width_hook.js`. This is intentional: it is the only way to
inject saved widths without losing the render race, and it keeps the patched
surface area tiny. On each Odoo major upgrade, re-sync it with a short,
mechanical diff:

1. Copy the new upstream `web/static/src/views/list/column_width_hook.js`
   over the fork.
2. Re-apply the changes marked `// NOVALYFT`, in this order:
   - **storage import** — `import { loadWidths, saveWidths, clearWidths } from "./width_store";`
   - **rename / export + param** — `export function usePersistentColumnWidths(tableRef, getState, getStorageKey)`
   - **seed-on-first-compute** — seed `startingWidths` from `loadWidths(getStorageKey())`, hash-gated, on the first `!columnWidths` branch;
   - **save-on-resize** — `saveWidths(getStorageKey(), { hash, widths })` in `stopResize`;
   - **`resetView`** — add the function and export it in the returned API;
   - **always-register-effects** — remove the `renderer.constructor.useMagicColumnWidths` guard so the effects/listeners are registered unconditionally (a bare block), and drop the now-unused `const renderer`.
3. Re-run the Hoot suite **and** the tour (below). All green.

Keeping the fork a small, clearly-marked diff turns each upgrade into a
~5-minute mechanical re-sync — and is itself a differentiator versus modules
that silently break on upgrade.

## Tests

The module ships with both a Hoot unit-test suite (storage round-trip, restore
on re-mount, hash-mismatch invalidation, exact storage-key string, RTL,
quota/exception degradation) and a `web_tour` integration tour driven from a
Python `HttpCase` (resize a Contacts list column → switch views and back →
assert the width persisted).

Run them on a fresh test database:

```
odoo-bin -d <db> -i list_column_widths_persist --test-enable \
         --test-tags=/list_column_widths_persist --stop-after-init
```

On Odoo.sh, tests run automatically during the staging-branch build.

## License

LGPL-3.

## Author / Maintainer

Novalyft Solutions.
