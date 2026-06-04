# SPEC — `list_column_widths_persist`

**Persistent List Column Widths — Remember Resized Columns (Odoo 19)**
Author/maintainer: Novalyft Solutions · License: LGPL-3 · Target: Odoo 19.0 Community **and** Enterprise · Repo branch: `19.0`

---

## 1. Objective

Make manually-resized list (tree) view column widths **persist** across navigation, view switches, and browser sessions, per view, for every user. Standard Odoo 19 forgets resized widths the moment the list renderer unmounts. This module fixes that with no configuration required.

This is an open-source addon for the `novalyft/odoo-addons` monorepo, published to the Odoo Apps Store, and must match the conventions already used by the `unearned_revenue_recognition` module in that repo.

---

## 2. Locked product decisions

| # | Decision | Value |
|---|----------|-------|
| 1 | Persistence backend | **`localStorage` only** (per browser profile). No server model, no DB writes. Storage access goes through a thin abstraction so a future server-sync backend can be added without touching the renderer. |
| 2 | Technical name / display name | `list_column_widths_persist` / **"Persistent List Column Widths — Remember Resized Columns"** |
| 3a | Per-view "Reset column widths" control | **IN** |
| 3b | Per-user enable/disable toggle | **OUT** — always on for all users |
| 3c | Admin-defined org-wide default widths | **OUT** (possible v1.1) |
| 4 | Scope | **All list views, including x2many embedded lists. No model exclusions.** |

---

## 3. Hard technical context (verified against Odoo 19 source)

> Claude Code: **do not rely on this section as ground truth — re-read the actual files** in the local Odoo install (see §10) before implementing. This is the orientation.

The entire column-width behavior lives in one hook:
`odoo/addons/web/static/src/views/list/column_width_hook.js` → `export function useMagicColumnWidths(tableRef, getState)`.

It is consumed **only** by `ListRenderer` (`odoo/addons/web/static/src/views/list/list_renderer.js`):

```js
// list_renderer.js (~line 99)
export class ListRenderer extends Component {
    static useMagicColumnWidths = true;            // ~line 104
    ...
    setup() {
        ...
        const key = this.createViewKey();           // ~line 140 — STABLE per-view key
        ...
        this.columnWidths = useMagicColumnWidths(this.tableRef, () => ({   // ~line 267
            columns: this.columns,
            isEmpty: !this.props.list.records.length || this.props.list.model.useSampleModel,
            hasSelectors: this.hasSelectors,
            hasOpenFormViewColumn: this.hasOpenFormViewColumn,
            hasActionsColumn: this.hasActionsColumn,
        }));
    }
    // createViewKey() (~line 600): builds an identifier from
    //   model, viewMode, viewId, (x2many) relationalField, subViewType, + sorted field names.
    //   Odoo already reuses this for the optional-columns localStorage key
    //   (`optional_fields,${key}`) and debug-open-view key.
}
```

Facts that drive the design:

1. **Widths are never persisted.** Inside the hook, computed widths live in a closure variable `columnWidths` (a plain array indexed by `<thead> th`, content-width basis, i.e. padding subtracted). It dies on unmount. On a manual drag, `stopResize` writes the final DOM widths into that closure to "freeze" them for the current render cycle only.

2. **Three events deliberately forget widths** (call `unsetWidths`, setting the closure to `null`): a change in the column-set hash (`columns.map(c => c.id).join("/") + "/" + headers.length`), a window `resize`, and the table transitioning from empty→populated. These must keep working — they are correctness, not bugs.

3. **You cannot inject saved widths from outside the hook.** Any DOM width you set externally is overwritten on the next render when the hook's `useEffect(forceColumnWidths)` re-applies its own frozen array. An "overlay" patch loses this race and flickers. **Therefore we vendor (fork) the hook** with a few marked edits and swap it into `ListRenderer`.

4. **`createViewKey()` is the storage-key seam.** Reusing it gives per-view, x2many-subview-aware, field-set-aware keys for free, and the column-set hash gives automatic invalidation when the arch's columns change.

5. **Asset bundles (verified in `web/__manifest__.py`):** runtime → `web.assets_backend`; Hoot unit tests → `web.assets_unit_tests`; tour files for `HttpCase` → `web.assets_tests`.

---

## 4. Architecture

```
ListRenderer (patched)
  └── this.columnWidths = usePersistentColumnWidths(tableRef, getState, getStorageKey)
                                   │
                                   ├── (vendored fork of useMagicColumnWidths)
                                   ├── seed startingWidths from storage on first compute (hash-gated)
                                   ├── save widths to storage on resize end
                                   ├── resetView() — clear storage + recompute
                                   └── storage via widthStore abstraction
                                                         └── localStorage backend (v1)
```

- **Vendored hook** `persistent_column_width_hook.js` = byte-for-byte copy of upstream `column_width_hook.js`, exporting `usePersistentColumnWidths`, with exactly the edits in §6.2. Every edit is tagged `// NOVALYFT:` so the per-version re-sync (§11) is mechanical.
- **Patch** `list_renderer_patch.js` neuters the native hook's side effects and swaps in ours (§6.3).
- **Reset UX** via OWL template inheritance adding a dropdown item (§6.4).
- **Storage abstraction** `width_store.js` (§6.5) — single module that knows about `localStorage`; everything else calls `loadWidths(key)` / `saveWidths(key, payload)` / `clearWidths(key)`.

---

## 5. File / folder layout

```
list_column_widths_persist/
├── __init__.py                       # empty (no Python models)
├── __manifest__.py
├── README.md
├── static/
│   ├── description/
│   │   ├── icon.png                  # TODO: Mohamad supplies (placeholder ok)
│   │   ├── cover_screenshot.png      # TODO: Mohamad supplies
│   │   └── index.html                # Apps Store long description (mirror unearned module)
│   ├── src/
│   │   ├── width_store.js
│   │   ├── persistent_column_width_hook.js
│   │   ├── list_renderer_patch.js
│   │   └── list_renderer_patch.xml   # template inheritance: "Reset column widths" entry
│   └── tests/
│       ├── persistent_column_width.test.js   # Hoot unit tests
│       └── tours/
│           └── persist_widths_tour.js        # web_tour integration tour
└── tests/
    ├── __init__.py
    └── test_persist_tour.py          # HttpCase that runs the tour
```

> The `tests/` Python package exists **only** to launch the browser tour via `HttpCase`. There are no business models, no `security/`, no `data/`.

---

## 6. Detailed implementation requirements

### 6.1 `__manifest__.py`

Mirror the `unearned_revenue_recognition` manifest style exactly (author, maintainer, website, support, price/currency block, `images` with cover-first + `_screenshot` suffix convention). Concretely:

```python
{
    "name": "Persistent List Column Widths — Remember Resized Columns",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": (
        "Remember manually resized list view column widths across navigation, "
        "view switches, and sessions — per view, for every user. Zero config. "
        "Works on all list views including embedded one2many/many2many lists. "
        "Odoo 19 Community and Enterprise."
    ),
    "description": """ ... RST long description, sections: Why this module / How it works /
                       Highlights / Limitations / Keywords ... """,
    "author": "Novalyft Solutions",
    "maintainer": "Novalyft Solutions",
    "website": "https://novalyftsolutions.com",
    "support": "m.hassan@novalyftsolutions.com",
    "license": "LGPL-3",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "list_column_widths_persist/static/src/**/*.js",
            "list_column_widths_persist/static/src/**/*.xml",
        ],
        "web.assets_unit_tests": [
            "list_column_widths_persist/static/tests/**/*.test.js",
        ],
        "web.assets_tests": [
            "list_column_widths_persist/static/tests/tours/**/*.js",
        ],
    },
    "images": ["static/description/cover_screenshot.png"],
    "price": 0.00,
    "currency": "USD",
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

> Verify the glob behavior against the local Odoo asset loader; if `**` globs are not honored in this build, list files explicitly. Ensure the backend glob never picks up `*.test.js` or the tour files.

### 6.2 `persistent_column_width_hook.js` — the vendored fork

Start from an **exact copy** of the local `column_width_hook.js`. Apply only these edits, each tagged `// NOVALYFT:`:

1. **Imports** — add:
   ```js
   import { loadWidths, saveWidths, clearWidths } from "./width_store"; // NOVALYFT
   ```

2. **Rename + add param** — change the export signature to:
   ```js
   export function usePersistentColumnWidths(tableRef, getState, getStorageKey) { // NOVALYFT
   ```

3. **Seed from storage on first compute.** Locate the block in `forceColumnWidths` (after `hash` has been recomputed for this pass) that reads:
   ```js
   if (!columnWidths || allowedWidthDiff > 0) {
       columnWidths = computeWidths(table, state, allowedWidth, columnWidths);
   }
   ```
   Replace with:
   ```js
   if (!columnWidths) {                                            // NOVALYFT
       const stored = loadWidths(getStorageKey());                 // NOVALYFT
       const seed =                                                // NOVALYFT
           stored &&                                               // NOVALYFT
           stored.hash === hash &&                                 // NOVALYFT
           Array.isArray(stored.widths) &&                         // NOVALYFT
           stored.widths.length === headers.length                 // NOVALYFT
               ? stored.widths                                     // NOVALYFT
               : null;                                             // NOVALYFT
       columnWidths = computeWidths(table, state, allowedWidth, seed); // NOVALYFT
   } else if (allowedWidthDiff > 0) {                              // NOVALYFT
       columnWidths = computeWidths(table, state, allowedWidth, columnWidths);
   }
   ```
   Rationale: passing the stored widths as `startingWidths` reuses Odoo's own min/max + 100%-fit math, so restored widths adapt cleanly to the current container width. Hash gating prevents applying stale widths to a changed column set.

4. **Save on resize end.** In `stopResize`, immediately after the line that recomputes `columnWidths` from the DOM:
   ```js
   columnWidths = headers.map(
       (th) => th.getBoundingClientRect().width - getHorizontalPadding(th)
   );
   saveWidths(getStorageKey(), { hash, widths: columnWidths });    // NOVALYFT
   ```

5. **Expose `resetView()`** in the returned API:
   ```js
   function resetView() {                                          // NOVALYFT
       clearWidths(getStorageKey());                               // NOVALYFT
       resetWidths();                                              // NOVALYFT
   }                                                               // NOVALYFT
   ...
   return {
       get resizing() { return _resizing; },
       onStartResize,
       resetWidths,
       resetView,                                                  // NOVALYFT
   };
   ```

6. **Always register effects.** The upstream guard `if (renderer.constructor.useMagicColumnWidths) { useEffect(forceColumnWidths); ... }` must be changed so our hook always registers its effects (we invoke it deliberately and have neutered the native flag — see §6.3). Remove the `renderer.constructor.useMagicColumnWidths` condition (keep the effect/listener body). Tag the change `// NOVALYFT`.

> Do **not** otherwise modify the width math, the freeze logic, or the RTL delta handling — they are inherited and must keep working.

### 6.3 `list_renderer_patch.js` — wiring

```js
import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { usePersistentColumnWidths } from "./persistent_column_width_hook";

// Capture the original intent, then neuter the native hook's side effects so they
// don't run alongside ours. We only swap in our hook where magic widths were wanted.
const NATIVE_MAGIC = ListRenderer.useMagicColumnWidths;
ListRenderer.useMagicColumnWidths = false;

patch(ListRenderer.prototype, {
    setup() {
        super.setup(); // native hook runs but, with the flag off, registers no effects
        if (NATIVE_MAGIC) {
            this.columnWidths = usePersistentColumnWidths(
                this.tableRef,
                () => ({
                    columns: this.columns,
                    isEmpty:
                        !this.props.list.records.length ||
                        this.props.list.model.useSampleModel,
                    hasSelectors: this.hasSelectors,
                    hasOpenFormViewColumn: this.hasOpenFormViewColumn,
                    hasActionsColumn: this.hasActionsColumn,
                }),
                () => `column_widths,${this.createViewKey()}`
            );
        }
    },

    // Called by the "Reset column widths" dropdown item (see template).
    onResetColumnWidths() {              // NOVALYFT
        this.columnWidths.resetView();
    },
});
```

Notes:
- The `getState` object **must** match the current local `list_renderer.js` shape — copy it from there, do not trust this snippet if the source differs.
- Existing renderer template calls (`this.columnWidths.onStartResize(...)`, `this.columnWidths.resizing`) keep working because the API names are preserved. No change to resize wiring.

### 6.4 `list_renderer_patch.xml` — "Reset column widths" entry

- Use OWL template inheritance (`<t t-inherit="web.ListRenderer" t-inherit-mode="extension">`) to add a `<DropdownItem>` labelled **"Reset column widths"** into the optional-columns dropdown, with `onSelected.bind` (or the idiom used by the sibling optional-field items) calling `onResetColumnWidths()`.
- `DropdownItem` is already in `ListRenderer.components`, so reuse it; find the existing optional-fields dropdown markup in the local `list_renderer.xml` and xpath a sibling item in.
- **Visibility fix:** the optional-columns dropdown only renders when the view has optional columns. So the reset entry would be hidden on views with no optional columns. Extend the getter that gates the dropdown's visibility (locate it in `list_renderer.js` — it is the one backing the dropdown's `t-if`, around the optional-fields logic) so the dropdown also renders when `loadWidths(\`column_widths,${this.createViewKey()}\`)` returns a saved entry for the current view. Keep this minimal and well-commented.
- Label must be translatable (`_t`).

### 6.5 `width_store.js` — storage abstraction

```js
import { browser } from "@web/core/browser/browser";

// payload shape: { hash: string, widths: number[] }  (widths are content-width px, padding excluded)

export function loadWidths(key) {
    try {
        const raw = browser.localStorage.getItem(key);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null; // private mode / corrupt value / quota
    }
}

export function saveWidths(key, payload) {
    try {
        browser.localStorage.setItem(key, JSON.stringify(payload));
    } catch {
        /* quota or private mode: silently ignore — persistence is best-effort */
    }
}

export function clearWidths(key) {
    try {
        browser.localStorage.removeItem(key);
    } catch {
        /* ignore */
    }
}
```

This is the **only** module that references `localStorage`. A future server-sync backend swaps here behind the same three functions.

---

## 7. Behavior, invalidation, and edge cases

- **Per view, per user:** widths key off `createViewKey()` (model + viewId + x2many path + sorted field set). `localStorage` is per browser profile ⇒ effectively per user on a machine.
- **x2many embedded lists:** supported automatically — `createViewKey()` includes the nested sub-view path.
- **Column-set change** (optional column toggled, arch field added/removed): hash mismatch ⇒ stored widths ignored, fresh compute. Saving a resize afterward stores under the new hash.
- **Window resize:** native `unsetWidths` still clears the in-memory closure; next compute re-seeds from storage and refits to the new width. (This is an intentional improvement over stock, which discards manual widths on window resize.)
- **Empty→populated transition:** unchanged native behavior.
- **RTL:** inherited from upstream delta handling; must be covered by a test (relevant to Arabic-locale clients).
- **Private/incognito or quota errors:** all storage ops are wrapped; the module degrades to stock behavior, never throws.
- **Reset:** clears the stored entry for the current view and recomputes ideal widths immediately.

### Non-goals (v1)
- No server-side / cross-device sync (architecture leaves room for v1.1).
- No admin-defined org-wide default widths.
- No per-user on/off toggle.
- Renderers that *explicitly opted out* of magic widths (`static useMagicColumnWidths = false`) and subclass `ListRenderer` without redeclaring are out of scope; no standard Odoo renderer does this.

---

## 8. Testing requirements

The repo's contributing rule requires tests for new behavior. Ship **both**:

### 8.1 Hoot unit tests — `static/tests/persistent_column_width.test.js`
Model the file on the upstream list-view width/resize Hoot test (find it under `addons/web/static/tests/views/list/` in the local source) and its helpers (`@odoo/hoot`, `@web/.../tests/web_test_helpers`, `@odoo/hoot-dom`). Cover:
1. After a programmatic column resize, `localStorage` contains the key `column_widths,<createViewKey>` with a `{hash, widths}` payload.
2. Re-mounting the same view applies the stored widths to the headers (within ~1px tolerance).
3. A stored payload whose `hash` no longer matches the current column set is **ignored** (fresh ideal widths used).
4. The storage key equals `column_widths,${createViewKey()}` for a known arch (assert the exact string).
5. RTL: resizing in an RTL locale stores/restores correctly.
6. Quota/exception path: a throwing `localStorage` does not break rendering (stub `browser.localStorage`).

### 8.2 Integration tour — `static/tests/tours/persist_widths_tour.js` + `tests/test_persist_tour.py`
- Tour runs against the **Contacts (`res.partner`) list view** (always present): open list → drag a column's resize handle to a distinctly different width → switch to another view (e.g. kanban) and back to list (forces renderer unmount/remount) → assert the resized column header keeps the new width.
- Python `HttpCase` with `@tagged("post_install", "-at_install")` calling `self.start_tour(...)`.
- Use robust selectors (`.o_list_renderer table.o_list_table thead th[data-name="..."]`); keep tolerance generous.

### 8.3 Run before done
- JS: run the Hoot suite for this module.
- Python/tour: `odoo-bin -d <db> -i list_column_widths_persist --test-enable --test-tags=/list_column_widths_persist` (adjust to local runner). All green.

---

## 9. Documentation deliverables

- **`README.md`** (module root) mirroring the `unearned_revenue_recognition` README structure: title, one-paragraph what/why, Compatibility (19.0 Community + Enterprise), Business problem, How it works (technical: vendored hook + patch + `createViewKey` storage), Installation (drop into addons path / Odoo.sh branch link), Configuration ("none — zero config"), Limitations, **Maintainer note** (§11), License, Author.
- **`static/description/index.html`** — Apps Store long description; mirror the markup/structure of the existing module's `index.html` from the local repo (`/Users/mohamadhassan/Projects/odoo-custom-addon/unearned_revenue_recognition/static/description/index.html`).
- **Repo root `README.md`** — add a "Modules in this repository" entry for this module (same format as the existing one).
- Icon/screenshots: create the `static/description/` folder and reference `cover_screenshot.png` in the manifest; leave a clear `TODO` note that Mohamad supplies the real `icon.png` and `*_screenshot.png` assets (the `_screenshot` suffix + cover-first ordering is required for the Apps Store cover slot).

---

## 10. Local resources to read first (do not code from memory)

- **Full Odoo 19 Enterprise source:** `/Users/mohamadhassan/Projects/odoo-19.0+e.20260215`
  - Locate and read before implementing:
    - `…/addons/web/static/src/views/list/column_width_hook.js` (copy this for the fork)
    - `…/addons/web/static/src/views/list/list_renderer.js` (confirm `getState` shape, `createViewKey()`, the optional-columns dropdown getter)
    - `…/addons/web/static/src/views/list/list_renderer.xml` (find the optional-columns dropdown markup to xpath into)
    - the upstream list width/resize Hoot **test** under `…/addons/web/static/tests/views/list/`
    - `…/addons/web/__manifest__.py` (confirm bundle names already verified: `web.assets_backend`, `web.assets_unit_tests`, `web.assets_tests`)
  - Find exact paths with, e.g.: `find /Users/mohamadhassan/Projects/odoo-19.0+e.20260215 -path '*views/list/column_width_hook.js'`
- **Existing module to mirror conventions:** `/Users/mohamadhassan/Projects/odoo-custom-addon/unearned_revenue_recognition/` (manifest, README, `static/description/index.html`).
- **Repo:** `novalyft/odoo-addons`, branch `19.0`, LGPL-3, one-branch-per-version convention.

---

## 11. Maintainer note — per-version re-sync (put in README)

`persistent_column_width_hook.js` is a deliberate **vendored fork** of `web`'s `column_width_hook.js`. On each Odoo major upgrade:
1. Copy the new upstream `column_width_hook.js` over the fork.
2. Re-apply the changes marked `// NOVALYFT:` (rename/export, storage import, seed-on-first-compute, save-on-resize, `resetView`, always-register-effects).
3. Re-run the Hoot suite + tour.

This keeps the surface area tiny and the upgrade path a ~5-minute mechanical diff — and is itself a differentiator versus modules that silently break on upgrade.

---

## 12. Definition of done

- [ ] Module installs cleanly on Odoo 19 Community **and** Enterprise with `depends: ["web"]` only.
- [ ] Resizing any list column, navigating away (or switching views) and returning restores the width — in standard list views **and** x2many embedded lists.
- [ ] Widths persist across full browser-session reloads (localStorage).
- [ ] Toggling an optional column (changing the column set) correctly invalidates stored widths.
- [ ] Window resize keeps the user's widths (re-seeded + refit), no flicker.
- [ ] "Reset column widths" appears in the optional-columns dropdown and works; dropdown is reachable even on views without optional columns when a saved width exists.
- [ ] RTL verified.
- [ ] No console errors; private-mode/quota failures degrade gracefully to stock behavior.
- [ ] Hoot unit tests + tour all green.
- [ ] README (module + repo root) and `static/description/index.html` complete; manifest Apps-Store-ready; `// NOVALYFT:` markers present in the fork; maintainer re-sync note included.
- [ ] No business models, no `security/`, no `data/`. The only Python is the tour runner.
