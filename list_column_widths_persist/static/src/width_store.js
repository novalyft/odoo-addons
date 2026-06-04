import { browser } from "@web/core/browser/browser";

// Storage abstraction for persisted list column widths.
//
// This is the ONLY module that touches `localStorage`. Everything else calls loadWidths /
// saveWidths / clearWidths, so a future server-sync backend (v1.1) can be swapped in here
// behind the same three functions without touching the renderer or the hook.
//
// Payload shape: { hash: string, widths: number[] }
//   - hash:   the column-set hash from the hook (`${columns.map(c=>c.id).join("/")}/${headers.length}`)
//   - widths: content-width px per <thead> th (horizontal padding excluded)
//
// Every access is exception-wrapped: private/incognito mode, disabled storage, quota errors, or a
// corrupt value must never throw — the module degrades silently to stock Odoo behavior.

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
