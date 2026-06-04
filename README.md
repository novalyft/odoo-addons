# Odoo Custom Addons by Novalyft Solutions

Open-source Odoo modules maintained by [Novalyft Solutions](https://novalyftsolutions.com).

## Branches

Following the standard Odoo / OCA convention, this repository uses **one
branch per Odoo major version**:

- [`19.0`](https://github.com/novalyft/odoo-addons/tree/19.0) — current default
- Future: `20.0`, `21.0`, …

Check out the branch matching your Odoo version before installing. Each
version branch is independently maintained — fixes to one are
deliberately cherry-picked to the others rather than auto-propagated.

## Modules in this repository

### [list_column_widths_persist](./list_column_widths_persist) — Persistent List Column Widths

Makes manually-resized list (tree) view column widths **persist** across
navigation, view switches, and browser sessions — per view, for every user,
with no configuration required. Standard Odoo 19 forgets a column's resized
width the moment the list renderer unmounts; this module remembers it in the
browser and restores it the next time the view is shown.

**Highlights**

- Works on every list view, including embedded one2many / many2many lists — one
  prototype patch on `ListRenderer`, no model exclusions.
- Survives navigation, view switches, and full browser-session reloads.
- Widths keyed off Odoo's own `createViewKey()`; column-set changes invalidate
  stored widths automatically.
- Per-view **Reset column widths** entry in the optional-columns dropdown.
- Zero configuration — always on, for every user.
- Private-mode / quota-safe storage layer; degrades silently, never throws.
- Tiny vendored hook fork (every change tagged `// NOVALYFT`) for a ~5-minute
  per-version re-sync.
- Compatible with **Odoo 19 Community and Enterprise** (depends on `web` only).

See the [module README](./list_column_widths_persist/README.md) for the
mechanism, installation, and per-version maintainer note.

### [unearned_revenue_recognition](./unearned_revenue_recognition) — IFRS Unearned Revenue Recognition on Delivery

Defers revenue recognition from invoice posting to physical delivery, in line
with **IFRS 15 / ASC 606**. Customers are invoiced (often paid) upfront for
AR tracking, but the credit side is routed to an Unearned Revenue liability
account. Revenue is moved to Sales Revenue automatically when the
corresponding `stock.picking` is validated; returns reverse the recognition;
credit notes inherit the deferral account.

**Highlights**

- Three-level deferral-account fallback chain (product category → company
  default → Odoo Enterprise's native Deferred Revenue Account).
- Partial deliveries, backorders, returns, credit notes, multi-currency
  (invoice-date FX rate frozen), multi-company.
- Full audit trail via `x.revenue.recognition.line`; idempotent re-validation.
- Smart buttons on Sales Order, Customer Invoice, and Stock Picking forms.
- New report under **Accounting → Reporting → Deferred Revenue**.
- 22 unit tests.
- Compatible with **Odoo 19 Community and Enterprise**.

See the [module README](./unearned_revenue_recognition/README.md) for the
detailed configuration, walkthrough, and accounting pattern.

## Installation

1. Clone the branch that matches your Odoo version:
   ```bash
   git clone -b 19.0 https://github.com/novalyft/odoo-addons.git
   ```
2. Add the repository path to your Odoo `addons_path`:
   ```
   addons_path = ...,/path/to/odoo-addons
   ```
3. Restart Odoo with `-u all` or `-i <module_name>` and install via the Apps
   menu.

On **Odoo.sh**, link this repo to your project and configure it to track
the `19.0` branch. Modules become available automatically once the build
completes.

## License

All modules in this repository are released under [LGPL-3](./LICENSE).

## Contributing

Issues and pull requests are welcome. Please make sure new code:

- Passes the existing tests (`--test-tags=<module_name>`).
- Includes tests for new behavior.
- Follows Odoo 19 conventions (no `_sql_constraints`, no removed Odoo 18-era
  view-attrs, use `models.Constraint`, etc.).

## Author / Maintainer

[Novalyft Solutions](https://novalyftsolutions.com) — Odoo implementations
and custom development for the Levant, GCC, and beyond.
