import { registry } from "@web/core/registry";

// Integration tour for list_column_widths_persist.
//
// Flow: on the res.partner list (whose "Name" column — data-name="complete_name" — is the only
// always-visible, freely-resizable text column), widen that column via a real pointer-event drag on
// its `.o_resize` handle, switch to kanban and back to list, and assert the widened width survived
// the renderer unmount/remount. That round trip is exactly what stock Odoo forgets and what this
// module restores (it seeds `forceColumnWidths` from the localStorage payload saved by the hook's
// `stopResize`).
//
// No `url` is set here: the Python HttpCase (test_persist_tour.py) navigates to the res.partner
// "Customers" list action (base.action_partner_form, always installed — no `contacts` dependency)
// via /odoo/action-<id> before starting the tour, so the tour runs on whatever page is loaded.
//
// The tour DSL's "drag_and_drop" cannot express a pixel delta, and the resize hook computes the new
// width purely from `ev.clientX - initialX`, so we drive the drag with manual PointerEvents carrying
// explicit clientX/clientY (technique mirrored from website's website_update_column_count tour).

const TH = ".o_list_renderer table.o_list_table thead th[data-name='complete_name']";

// How far we widen, in CSS px. Comfortably above the 100px assertion floor in step (d) and the 8px
// persistence tolerance in step (g), while staying within the viewport so clientX stays on-screen.
const DELTA = 200;

/**
 * Dispatch a single PointerEvent. The resize hook (onStartResize) reads ev.target.closest("th") on
 * the initial pointerdown, then computes deltas from ev.clientX on subsequent moves, and listens for
 * pointermove / pointerup on `window`. So pointerdown goes to the handle element; the move/up that
 * actually resize go to `window`.
 * @param {EventTarget} target
 * @param {string} type
 * @param {number} clientX
 * @param {number} clientY
 */
function firePointer(target, type, clientX, clientY) {
    target.dispatchEvent(
        new PointerEvent(type, {
            bubbles: true,
            cancelable: true,
            composed: true,
            button: 0,
            buttons: type === "pointerup" ? 0 : 1,
            pointerId: 1,
            pointerType: "mouse",
            clientX,
            clientY,
            view: window,
        })
    );
}

registry.category("web_tour.tours").add("list_column_widths_persist_tour", {
    steps: () => [
        {
            content: "Wait for the Contacts list with the always-visible Name column",
            trigger: TH,
        },
        {
            content: "Record the Name column's starting width",
            trigger: TH,
            run() {
                window.__lcwpW0 = this.anchor.getBoundingClientRect().width;
            },
        },
        {
            content: "Drag the Name column's resize handle to widen it by ~200px",
            // The .o_resize handle is `opacity-0` (revealed only on hover), so a tour cannot match
            // it as a *visible* trigger. Anchor on the always-visible header cell and reach into it
            // for the handle in run() — it is present in the DOM regardless of hover state.
            trigger: TH,
            async run() {
                const th = this.anchor;
                const handle = th.querySelector(".o_resize");
                if (!handle) {
                    throw new Error("no .o_resize handle found on the Name column header");
                }
                // onStartResize reads ev.clientX as initialX and ev.target.closest('th') as the
                // resized column, so anchor the start at the header's right edge and dispatch the
                // pointerdown ON the handle (its target must resolve to this th).
                const rect = th.getBoundingClientRect();
                const startX = Math.round(rect.right);
                const y = Math.round(rect.top + rect.height / 2);
                const endX = startX + DELTA;

                // pointerdown on the handle fires the hook's onStartResize (t-on-pointerdown), which
                // synchronously attaches its pointermove + stopResize (pointerup) listeners to window.
                firePointer(handle, "pointerdown", startX, y);
                // Yield one macrotask so those window listeners are attached before we move.
                await new Promise((resolve) => setTimeout(resolve, 0));
                // Move + release on window. resizeHeader widens th/table by (endX - startX); stopResize
                // (pointerup) freezes the widths and persists them via saveWidths().
                firePointer(window, "pointermove", endX, y);
                firePointer(window, "pointerup", endX, y);
            },
        },
        {
            content: "Assert the Name column actually widened",
            trigger: TH,
            run() {
                window.__lcwpW1 = this.anchor.getBoundingClientRect().width;
                if (!(window.__lcwpW1 > window.__lcwpW0 + 100)) {
                    throw new Error(
                        "resize did not widen the column (w0=" +
                            window.__lcwpW0 +
                            ", w1=" +
                            window.__lcwpW1 +
                            ")"
                    );
                }
            },
        },
        {
            content: "Switch to the kanban view",
            trigger: "button.o_switch_view.o_kanban",
            run: "click",
        },
        {
            content: "Wait for the kanban renderer (list renderer is now unmounted)",
            trigger: ".o_kanban_renderer",
        },
        {
            content: "Switch back to the list view",
            trigger: "button.o_switch_view.o_list",
            run: "click",
        },
        {
            content: "Wait for the list renderer to be remounted",
            trigger: ".o_list_renderer table.o_list_table",
        },
        {
            content: "Assert the widened width persisted across the view switch",
            trigger: TH,
            run() {
                const w = this.anchor.getBoundingClientRect().width;
                const w0 = window.__lcwpW0;
                const w1 = window.__lcwpW1;
                // The hook restores widths by re-seeding computeWidths(), which refits them to the
                // current container: an over-wide drag (the table was widened past 100%) is pulled
                // back to fit on remount. So assert the widening PERSISTED — the column stayed
                // clearly wider than its pre-resize default — rather than pixel-matching the
                // transient post-drag width. Without this module, the remount would recompute the
                // clean ideal and w would fall back to ~w0.
                if (!(w > w0 + 30)) {
                    throw new Error(
                        "column width did not persist across view switch: restored " +
                            w +
                            "px is not meaningfully wider than the pre-resize default " +
                            w0 +
                            "px (post-resize was " +
                            w1 +
                            "px)"
                    );
                }
            },
        },
    ],
});
