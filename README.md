# Odoo 19 Custom Addons by Novalyft Solutions

Open-source Odoo 19 modules maintained by [Novalyft Solutions](https://novalyftsolutions.com).

## Modules in this repository

### [unearned_revenue_recognition](./unearned_revenue_recognition) — Unearned Revenue Recognition on Delivery

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
- 27 unit tests.
- Compatible with **Odoo 19 Community and Enterprise**.

See the [module README](./unearned_revenue_recognition/README.md) for the
detailed configuration, walkthrough, and accounting pattern.

## Installation

1. Clone this repository to a path Odoo can read:
   ```bash
   git clone https://github.com/novalyft/odoo-unearned-revenue-recognition.git
   ```
2. Add the repository path to your Odoo `addons_path`:
   ```
   addons_path = ...,/path/to/odoo-unearned-revenue-recognition
   ```
3. Restart Odoo with `-u all` or `-i <module_name>` and install via the Apps
   menu.

On **Odoo.sh**, link this repo to your project; modules become available
automatically once the build completes.

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
