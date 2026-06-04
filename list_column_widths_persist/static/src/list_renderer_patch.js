import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

import { usePersistentColumnWidths } from "./persistent_column_width_hook";
import { loadWidths } from "./width_store";

// Wire the vendored persistent-width hook into ListRenderer (and, through it, every x2many
// embedded list, since those use ListRenderer too). The native `useMagicColumnWidths` hook still
// runs via super.setup(), but we neuter its side effects so only our hook drives the widths.
patch(ListRenderer.prototype, {
    setup() {
        // Read THIS instance's opt-in BEFORE neutering, so subclasses that deliberately opt out
        // with `static useMagicColumnWidths = false` (e.g. hr_skills' ResumeListRenderer) stay
        // opted out instead of silently gaining persistence.
        const wantsMagic = this.constructor.useMagicColumnWidths;
        // Neuter the native hook's effects for this setup so they don't run alongside ours.
        // setup() is synchronous, so toggling + restoring the static around super.setup() is
        // race-free (control never yields between the two assignments).
        const ctor = this.constructor;
        const originalMagic = ctor.useMagicColumnWidths;
        ctor.useMagicColumnWidths = false;
        try {
            super.setup();
        } finally {
            ctor.useMagicColumnWidths = originalMagic;
        }
        if (wantsMagic) {
            // Cache the per-view storage key once, mirroring Odoo's own `this.keyOptionalFields`.
            // createViewKey() yields a per-model / per-view / x2many-subview-aware, field-set-aware
            // key, so widths are scoped per view for free.
            this.persistentColumnWidthsKey = `column_widths,${this.createViewKey()}`;
            // getState object copied verbatim from list_renderer.js (keep in sync on re-vendor).
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
                () => this.persistentColumnWidthsKey
            );
        }
    },

    // The optional-columns dropdown hosts our "Reset column widths" item. Stock only renders that
    // dropdown when the view has optional columns, so also render it when this view has a saved
    // width entry — that keeps the reset control reachable wherever a width was persisted. This
    // getter transitively feeds `hasActionsColumn` too, which renders the column hosting the
    // dropdown, so overriding it alone flips both render gates.
    get displayOptionalFields() {
        return super.displayOptionalFields || this.hasPersistedColumnWidths;
    },

    get hasPersistedColumnWidths() {
        return !!(this.persistentColumnWidthsKey && loadWidths(this.persistentColumnWidthsKey));
    },

    get resetColumnWidthsLabel() {
        return _t("Reset column widths");
    },

    onResetColumnWidths() {
        // Optional-chained: a no-op on renderers where our hook wasn't installed (opt-out subclass).
        this.columnWidths?.resetView?.();
    },
});
