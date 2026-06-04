import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { queryAll, queryAllProperties, resize } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    patchWithCleanup,
    webModels,
} from "@web/../tests/web_test_helpers";

import { browser } from "@web/core/browser/browser";
import { localization } from "@web/core/l10n/localization";

// Side-effect import: applies our global ListRenderer.prototype patch so that
// `usePersistentColumnWidths` (the vendored fork) drives the widths during these
// tests. Without this, the stock `useMagicColumnWidths` hook would run and nothing
// would be persisted. Must be at the very top, before any view is mounted.
import "@list_column_widths_persist/list_renderer_patch";

describe.current.tags("desktop");

const { ResCompany, ResPartner, ResUsers } = webModels;

// A small model with a handful of differently-typed fields, so each column gets a
// distinct ideal width (Char has only a min width and expands; Integer/Float/Date
// have hardcoded widths). Modeled on the upstream `Foo` model in column_widths.test.js.
class Foo extends models.Model {
    foo = fields.Char();
    text = fields.Text();
    int_field = fields.Integer();
    qux = fields.Float();
    date = fields.Date();

    _records = [
        { id: 1, foo: "yop", int_field: 10, qux: 0.4, date: "2017-01-25" },
        { id: 2, foo: "blip", int_field: 9, qux: 13, date: "2017-02-03" },
        { id: 3, foo: "gnap", int_field: 17, qux: -3, date: "2017-03-15" },
        { id: 4, foo: "blip", int_field: -4, qux: 9, date: "2017-04-20" },
    ];
}

defineModels([Foo, ResCompany, ResPartner, ResUsers]);

beforeEach(() => {
    // Width math depends on a stable viewport width and font, exactly as upstream.
    resize({ width: 800 });
    document.body.style.fontFamily = "sans-serif";
});

// IMPORTANT: each `mountView` appends a NEW `.o_action_manager` (with its own list
// table) to the fixture and does NOT unmount the previous one until end-of-test. So in
// the remount tests (2, 3, 5) two `.o_list_table`s coexist in the DOM. We therefore scope
// every read/interaction to the LAST-mounted renderer — that is the "fresh mount" whose
// widths we want to assert. Single-mount tests (1, 4, 6) also work through this scoping.
function lastRenderer() {
    const renderers = queryAll(".o_list_renderer");
    return renderers[renderers.length - 1];
}

function getColumnWidths() {
    return queryAllProperties("thead th", "offsetWidth", { root: lastRenderer() });
}

// Drag the first data column's resize handle to the middle of the next column — the
// upstream resize idiom from column_widths.test.js. The source handle lookup is scoped
// to the (currently only) renderer; the drop target `th:eq(2)` is unambiguous because at
// every drag in this suite exactly one list table exists (tests 2 & 5 resize on the first
// mount, before the second exists; tests 1, 4, 6 are single-mount).
async function resizeFooColumn() {
    await contains(`th:eq(1) .o_resize`, { visible: false, root: lastRenderer() }).dragAndDrop(
        `th:eq(2)`
    );
}

// The two-field arch used by tests 1, 3 and 4. Kept deliberately minimal (two primitive
// fields, no monetary/relational fields) so the requested `fieldNames` — and therefore
// `createViewKey()` — are predictable for the exact-key assertion in test 4.
const SIMPLE_ARCH = `
    <list>
        <field name="foo"/>
        <field name="int_field"/>
    </list>`;

// Arch used by the restore tests (2 and 5). BOTH data columns are width-elastic
// (Char has only a min width; Text has a wide [80, 1200] range), so:
//   * the ideal layout splits the available space between them (neither is maximal,
//     leaving foo clear room to be dragged wider), and
//   * on restore, Odoo's refit shrinks the (overflowing) stored widths *proportionally*
//     across both elastic columns — so the user's "foo much wider than text" preference
//     is preserved as an ordering, rather than one column being pinned to a hardcoded
//     width. That makes the restoration observable and deterministic. `text` is left
//     empty in the records so its ideal width stays moderate.
const ELASTIC_ARCH = `
    <list>
        <field name="foo"/>
        <field name="text"/>
    </list>`;
// Header index of the "foo" column for ELASTIC_ARCH: [selector(0), foo(1), text(2)].
const FOO_COL = 1;

/**
 * Returns the single "column_widths," key currently in storage (there is exactly
 * one per mounted view in these tests), or undefined if none has been written yet.
 */
function getStoredWidthKey() {
    return Object.keys(browser.localStorage).find((k) => k.startsWith("column_widths,"));
}

// 1. A programmatic resize persists a well-formed payload under a "column_widths," key.
test(`resize persists a {hash, widths} payload under a column_widths key`, async () => {
    await mountView({ type: "list", resModel: "foo", arch: SIMPLE_ARCH });

    // No width has been saved before the user resizes anything.
    expect(getStoredWidthKey()).toBe(undefined);

    await resizeFooColumn();

    const key = getStoredWidthKey();
    expect(key).toMatch(/^column_widths,/);

    const payload = JSON.parse(browser.localStorage.getItem(key));
    expect(typeof payload.hash).toBe("string");
    expect(Array.isArray(payload.widths)).toBe(true);
    expect(payload.widths.length).toBeGreaterThan(0);
    expect(payload.widths.every((w) => typeof w === "number")).toBe(true);
    // The hash encodes the column-set: `${columns.map(c=>c.id).join("/")}/${headers.length}`.
    // For this arch there are 3 ths (selector + foo + int_field), so the hash ends in "/3".
    expect(payload.hash).toMatch(/\/3$/);
});

// 2. Stored widths are restored on a fresh mount of the SAME arch.
//
// Assumptions (see returned summary, test 2):
//   (a) Hoot resets localStorage only BETWEEN tests, not within one — so a payload
//       saved by the first mount is still present for the second mount in this test.
//   (b) The fork restores stored widths by *seeding* Odoo's width computation
//       (`startingWidths`), which then REFITS them to the current container (min/max
//       clamping + 100%-fit). A grow-resize overflows the table, so the restored widths
//       are the stored widths *shrunk back to fit the 800px viewport* — they are NOT
//       pixel-equal to the over-wide post-resize widths. The meaningful, deterministic
//       restoration signal is therefore: after remount, the "foo" column is clearly
//       WIDER than it is on a clean (no-persistence) mount, and two successive restores
//       agree within margin 3.
test(`stored widths are restored on a fresh mount of the same view`, async () => {
    // First mount: storage is empty, so this shows the genuine ideal layout. Capture
    // the ideal "foo" width as the no-persistence baseline.
    await mountView({ type: "list", resModel: "foo", arch: ELASTIC_ARCH });
    const idealWidths = getColumnWidths();
    expect(idealWidths.length).toBe(3);

    // Drag "foo" wider. This overflows the table and saves the (over-wide) widths.
    await resizeFooColumn();
    const resizedFooWidth = getColumnWidths()[FOO_COL];
    expect(resizedFooWidth).toBeGreaterThan(idealWidths[FOO_COL]);
    expect(getStoredWidthKey()).toMatch(/^column_widths,/);

    // Fresh mount #1 of the same arch: seeds from storage and refits to 800px.
    await mountView({ type: "list", resModel: "foo", arch: ELASTIC_ARCH });
    const restoredWidths = getColumnWidths();
    // Our patch surfaces the optional-columns / reset-dropdown column (a trailing th) once a width
    // has been persisted for this view (displayOptionalFields -> hasActionsColumn), so the seeded
    // remount has exactly one MORE column than the clean ideal mount above.
    expect(restoredWidths.length).toBe(idealWidths.length + 1);
    // The saved "foo is wide" preference survived the remount: foo is wider than its
    // clean ideal width (and wider than the neighbouring text column).
    expect(restoredWidths[FOO_COL]).toBeGreaterThan(idealWidths[FOO_COL]);
    expect(restoredWidths[FOO_COL]).toBeGreaterThan(restoredWidths[FOO_COL + 1]);

    // Fresh mount #2: restoration is deterministic, so it reproduces mount #1's widths
    // within margin 3 (this is the margin-3 equality the task asks for, applied to the
    // genuinely comparable pair: two restores under the same container width).
    await mountView({ type: "list", resModel: "foo", arch: ELASTIC_ARCH });
    const restoredAgain = getColumnWidths();
    restoredAgain.forEach((width, index) =>
        expect(width).toBeCloseTo(restoredWidths[index], { margin: 3 })
    );
});

// The exact storage key this SIMPLE_ARCH view uses. Pinned precisely (and independently
// re-verified) by test 4 below; reused here so test 3 can pre-seed the right entry
// without first mounting. See test 4 for the full derivation of every segment.
const SIMPLE_ARCH_KEY = "column_widths,foo,list,-1,foo,int_field";

// 3. A stored payload whose hash does NOT match the current column set is ignored.
test(`a stored payload with a mismatched hash is ignored (fresh ideal widths used)`, async () => {
    // Capture the genuine ideal "foo" width from a clean mount with empty storage, to
    // show the bogus widths are not applied. (Here only the SIMPLE_ARCH columns exist:
    // selector + foo + int_field.)
    await mountView({ type: "list", resModel: "foo", arch: SIMPLE_ARCH });
    const idealFooWidth = getColumnWidths()[1]; // [selector(0), foo(1), int_field(2)]

    // Pre-seed storage with widths under a hash that CANNOT match the real column set.
    // The bogus widths are deliberately absurd (all 999) so that, if they were ever
    // applied, a header would balloon far beyond the 800px viewport.
    browser.localStorage.setItem(
        SIMPLE_ARCH_KEY,
        JSON.stringify({ hash: "nope", widths: [999, 999, 999] })
    );

    // Mount the same arch again. Because the stored hash ("nope") != the current
    // column-set hash, the fork rejects the seed and computes ideal widths from scratch.
    // (Note: a saved payload also flips on the optional-columns/actions column via our
    // patch, so this second table has a trailing actions th — that's expected and
    // irrelevant to "are the bogus widths applied?".)
    await mountView({ type: "list", resModel: "foo", arch: SIMPLE_ARCH });

    const widths = getColumnWidths();
    // None of the columns adopted the bogus 999px width: every header fits inside the
    // 800px viewport, and "foo" is close to its genuine ideal width (the small delta
    // from the added actions column stays within a few px).
    widths.forEach((width) => expect(width).toBeLessThan(800));
    // "foo" got a real, freshly-computed width — close to its genuine ideal, NOT the bogus 999.
    // The margin is generous because the stale saved key still makes our patch surface the
    // optional-columns / reset-dropdown column (a narrow trailing th), which slightly redistributes
    // the 100%-fit so "foo" lands a little under its no-extra-column ideal.
    expect(widths[1]).toBeCloseTo(idealFooWidth, { margin: 40 });
});

// 4. The storage key equals "column_widths," + createViewKey() for a known arch.
//
// createViewKey() (web/.../list_renderer.js) builds, for a NON-nested list:
//     [model, viewMode, viewId, ...sortedFieldNames].join(",")
//   = "foo" + "," + "list" + "," + viewId + "," + sorted(fieldNames)
//
// Assumption (per task note for test 4): `mountView` with an inline `arch` assigns
// viewId = -1. This is pinned in the upstream test harness:
//   - view_test_helpers.js parseViewProps(): `viewProps.viewId ??= -1` when an arch
//     is given;
//   - mock_model.js findView(): `const actualViewId = Number(viewId) || false`, and
//     Number(-1) === -1 (truthy), so the resolved view id stays -1;
//   - view.js sets `env.config.viewId = viewDescription.id` (= -1), which is what
//     createViewKey() reads.
// The sorted field set for this arch is exactly ["foo", "int_field"] — only the two
// declared fields, with no implicit id/display_name. This matches the upstream
// `optional_fields` key precedent, which uses the SAME createViewKey():
// list_view.test.js asserts `optional_fields,foo,list,42,foo,m2o,reference` for an arch
// declaring exactly foo/m2o/reference. ("foo" < "int_field" lexically: 'f' < 'i'.)
// We assert BOTH the exact string AND the structural prefix/suffix, so a future change in
// how the harness assigns viewId still leaves a precise, readable failure.
test(`storage key equals "column_widths," + createViewKey()`, async () => {
    await mountView({ type: "list", resModel: "foo", arch: SIMPLE_ARCH });

    // Materialize the key by performing a resize (the only path that writes it).
    await resizeFooColumn();
    const key = getStoredWidthKey();

    // Exact string (preferred): model=foo, viewMode=list, viewId=-1, sorted fields.
    expect(key).toBe("column_widths,foo,list,-1,foo,int_field");

    // Structural belt-and-suspenders, in case the harness ever changes the viewId:
    // prefix is "column_widths,<model>,list," and the key ends with the sorted field list.
    expect(key.startsWith("column_widths,foo,list,")).toBe(true);
    expect(key.endsWith(",foo,int_field")).toBe(true);
});

// 5. RTL: widths are persisted AND restored on remount.
//
// Same restore mechanics as test 2 (seed + refit, see that test's assumptions). The
// extra wrinkle is direction: in RTL the resize handler negates the drag delta
// (`delta = -delta`), so dragging the handle the same screen direction moves "foo" the
// OPPOSITE way than in LTR. We therefore assert restoration in a direction-agnostic way:
//   * a payload with 3 numeric widths is stored, and
//   * the restored "foo" width clearly differs from the clean (no-persistence) RTL ideal
//     — proving the stored widths were applied — and two successive restores agree
//     within margin 3 (deterministic restoration).
test(`RTL: widths persist and restore on remount`, async () => {
    // Must be patched before mount: the resize handler reads localization.direction to
    // flip the drag delta sign, and date-width computation also branches on it.
    patchWithCleanup(localization, { direction: "rtl" });

    // Clean RTL mount: empty storage -> ideal layout. Baseline for the "foo" column.
    await mountView({ type: "list", resModel: "foo", arch: ELASTIC_ARCH });
    const idealFooWidth = getColumnWidths()[FOO_COL];

    await resizeFooColumn();
    const key = getStoredWidthKey();
    expect(key).toMatch(/^column_widths,/);
    const payload = JSON.parse(browser.localStorage.getItem(key));
    expect(Array.isArray(payload.widths)).toBe(true);
    expect(payload.widths.length).toBe(3);

    // Fresh mount #1 (still RTL): seeds from storage and refits.
    await mountView({ type: "list", resModel: "foo", arch: ELASTIC_ARCH });
    const restored1 = getColumnWidths();
    // Restoration had a visible effect on "foo" (resized away from its ideal width),
    // regardless of whether RTL grew or shrank it.
    expect(Math.abs(restored1[FOO_COL] - idealFooWidth)).toBeGreaterThan(3);

    // Fresh mount #2: deterministic restoration reproduces mount #1 within margin 3.
    await mountView({ type: "list", resModel: "foo", arch: ELASTIC_ARCH });
    const restored2 = getColumnWidths();
    restored2.forEach((width, index) =>
        expect(width).toBeCloseTo(restored1[index], { margin: 3 })
    );
});

// 6. Quota / exception path: storage that throws on every access must not break the list.
test(`storage that throws is swallowed; list still renders and is resizable`, async () => {
    // Simulate a storage backend that throws on every access to OUR keys (a quota error, or a
    // locked-down / incognito profile). width_store.js wraps every access in try/catch, so nothing
    // should propagate. The throw is scoped to "column_widths," keys, delegating all other keys to
    // the real (Hoot mock) storage: Odoo's own services read localStorage during env setup, so a
    // blanket-throwing stub would break mountView itself instead of exercising this module.
    const real = browser.localStorage;
    const failIfOurs = (key) => {
        if (typeof key === "string" && key.startsWith("column_widths,")) {
            throw new Error("simulated localStorage failure (quota / private mode)");
        }
    };
    patchWithCleanup(browser, {
        localStorage: {
            getItem: (key) => (failIfOurs(key), real.getItem(key)),
            setItem: (key, value) => (failIfOurs(key), real.setItem(key, value)),
            removeItem: (key) => (failIfOurs(key), real.removeItem(key)),
            clear: () => real.clear(),
            key: (i) => real.key(i),
            get length() {
                return real.length;
            },
        },
    });

    await mountView({ type: "list", resModel: "foo", arch: SIMPLE_ARCH });

    // The list rendered despite loadWidths() throwing during the first width compute.
    expect(`.o_list_table`).toHaveCount(1);
    expect(`.o_list_table thead th`).toHaveCount(3);

    // And a resize (which calls the throwing setItem via saveWidths) doesn't blow up.
    await resizeFooColumn();
    expect(`.o_list_table thead th`).toHaveCount(3);
});
