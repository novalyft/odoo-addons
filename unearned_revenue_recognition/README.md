# Unearned Revenue Recognition on Delivery

Generic, reusable Odoo 19 module that defers revenue recognition from invoice
posting to physical delivery in line with IFRS 15 / ASC 606. Built for retail
/ e-commerce / wholesale scenarios where the customer is invoiced (often
paid) upfront but goods are delivered later — sometimes in multiple shipments.

Compatible with **Odoo 19 Community and Enterprise**. The native Enterprise
Deferred Revenue Account is detected at runtime if `account_accountant` is
installed, but is never required.

## Business problem

In retail prepayment, the standard Odoo journal sequence is:

```
ON INVOICE:           Dr. Accounts Receivable    Cr. Sales Revenue (P&L)
                                                 Cr. VAT Payable
ON PAYMENT:           Dr. Bank                   Cr. Accounts Receivable
```

This recognizes revenue too early. Under IFRS 15 / ASC 606 revenue is
recognized only when the performance obligation (delivery of goods) is
satisfied. This module changes the pattern to:

```
ON INVOICE:           Dr. Accounts Receivable    Cr. Unearned Revenue (Balance Sheet liability)
                                                 Cr. VAT Payable
ON PAYMENT:           Dr. Bank                   Cr. Accounts Receivable
ON DELIVERY (auto):   Dr. Unearned Revenue       Cr. Sales Revenue (P&L)
ON RETURN  (auto):    Dr. Sales Revenue          Cr. Unearned Revenue
```

VAT is still recognized at invoice posting (correct per most tax-point rules,
including the Lebanese / GCC pattern). Only the revenue side is deferred.

## Installation

1. Drop `unearned_revenue_recognition/` into an Odoo 19 addons path. On
   Odoo.sh, commit the folder at the repo root next to any other addon
   folders.
2. Restart Odoo with that addons path included:
   `./odoo-bin -d <db> --addons-path=...,/path/to/odoo-custom-addon -u all`
3. From the Apps screen, search for "Unearned Revenue Recognition" and
   install.

Dependencies: `account`, `sale_management`, `stock`, `sale_stock` — all
shipped with standard Odoo.

## Configuration

Configure these in order of granularity — each level overrides the broader
one:

1. **Per product category** (recommended for most setups).
   `Inventory → Configuration → Product Categories → <category>`. The new
   **Unearned Revenue Account** field sets the deferral target for every
   product in that category.

2. **Company default** (fallback when categories are not configured).
   `Accounting → Configuration → Settings → Customer Invoices → Unearned
   Revenue Recognition`:
   - **Default Unearned Revenue Account** — company-wide deferral target.
   - **Recognition Journal** — Misc-type journal used for delivery-time
     recognition entries. Defaults to the first general journal if empty.

3. **Per product** (advanced — override the auto behavior).
   `Inventory → Products → <product> → Accounting tab`. The **Revenue
   Recognition Method** field:
   - **Automatic (default)** — storable/consumable goods recognize on
     delivery; services recognize on invoice.
   - **Recognize on invoice posting** — never defer, even for goods.
   - **Recognize on delivery** — always defer, including for services
     (a chatter warning is logged because a service has no downstream
     picking to trigger automatic recognition).

### Deferral-account fallback chain

When invoicing a sale-order line whose product wants deferral, the deferral
account is resolved in this order:

1. `product.categ_id.x_unearned_revenue_account_id`
2. `company.x_default_unearned_revenue_account_id`
3. `company.deferred_revenue_account_id` (Odoo Enterprise's native setting;
   skipped silently if `account_accountant` is not installed)
4. Standard income account — a warning is added to the invoice chatter so
   the accountant knows the deferral did not take effect.

## Usage walkthrough

1. **Configure** the deferral account on the relevant category (or as
   company default).
2. **Create the sales order** as usual.
3. **Confirm and invoice** — the invoice posts and credits the **Unearned
   Revenue** liability account instead of Sales Revenue. AR and VAT post
   normally.
4. **Register payment** — books a normal AR-clearing entry. Revenue is
   still not on the P&L.
5. **Validate the outgoing picking** — a new Misc-journal entry is posted
   automatically:
   ```
   Dr. Unearned Revenue   1000
       Cr. Sales Revenue       1000
   ```
   A row is written to the `x.revenue.recognition.line` audit trail.
6. **Partial delivery / backorder** — each picking validates only the
   portion of revenue tied to its delivered quantity. Backorders recognize
   their share when later validated.
7. **Return** — validating an incoming return picking posts the inverse
   entry automatically.
8. **Credit note** — credit notes for an SO-driven invoice inherit the
   deferral account, so the credit naturally offsets the unrecognized
   deferred balance and does NOT touch Sales Revenue.

Every Sales Order, Customer Invoice, and Stock Picking form has a **Revenue
Recognition** smart button that opens the filtered audit trail.

## Reporting

- **Accounting → Reporting → Deferred Revenue** — posted invoice lines still
  parked in a deferral account, grouped by partner. Use this to monitor
  "billed but not delivered" balances.
- **Accounting → Reporting → Revenue Recognition Lines** — full audit trail
  of every recognition and reversal event.
- **Sales Order header** — three computed fields visible once any
  recognition activity exists:
  - **Recognized Revenue** — net of non-reversal minus reversal recognition.
  - **Pending Recognition** — net invoiced-deferred amount minus already
    recognized.
  - **Revenue Recognition Status** — `not_started` / `partial` / `complete`.

## Idempotency, returns, cancellation

- **Idempotency**: each `stock.move` tracks how much has already been
  recognized via the `x.revenue.recognition.line` audit table. Re-validating
  a picking (or running the recognition trigger twice for any reason) cannot
  produce duplicate journal entries.
- **Returns**: an incoming return picking automatically posts the inverse
  recognition entry (`Dr. Sales Revenue / Cr. Unearned Revenue`) and writes
  a mirror audit row with `is_reversal=True`.
- **Invoice reset to draft / cancel**: every recognition entry generated
  from that invoice's lines is reversed automatically (`account.move.button_draft`
  / `button_cancel`). The corresponding audit rows are mirrored with
  `is_reversal=True`.
- **Picking cancellation**: Odoo 19's `stock.move._action_cancel` rejects
  any attempt to cancel a `done` move. Since recognition only fires AFTER
  a picking is `done`, the "cancel a recognized picking" path is physically
  unreachable in Odoo 19 — undo a delivery by validating a return instead.

## Known limitations

- **No time-based deferral.** This module recognizes on a discrete delivery
  event. For annual contracts, prepaid hours, subscriptions, or other
  time-spread revenue, use Odoo's native Enterprise Deferred Revenue feature
  instead.
- **Services forced to `on_delivery`.** When a service product is explicitly
  set to `on_delivery` but there is no downstream stock picking, the revenue
  stays parked in the Unearned Revenue account until you post a manual
  journal entry. The invoice chatter logs a warning in this case.
- **Manual invoices.** Invoices created without a sale.order link are NOT
  redirected, even if the product would normally defer. Create manual
  recognition entries if needed.

## Architecture / data flow

```
sale.order.line._prepare_invoice_line()        # set x_target_revenue_account_id + redirect account_id
        |
        v
account.move._post()                           # invoice posts, credits deferral
        |
        v
stock.picking._action_done()                   # outgoing non-return → _recognize_revenue
                                                  incoming return    → _reverse_revenue_recognition
        |
        v
account.move (recognition entry posted)
        |
        v
x.revenue.recognition.line (audit row)
```

Reversal paths (all funnel into `x.revenue.recognition.line` with
`is_reversal=True`):

- Return picking validation → `_reverse_revenue_recognition` posts a fresh
  account.move with inverted Dr/Cr proportional to the returned qty.
- Invoice reset / cancel → `account.move._reverse_linked_revenue_recognition`
  uses `_reverse_moves` to unwind every recognition entry generated from
  the affected invoice lines.

## Security

| Group (XML ID) | Access |
|---|---|
| `account.group_account_manager` (Accounting / Administrator) | read / write / create / delete |
| `account.group_account_invoice` (Accounting / Invoicing) | read / write / create, no delete |
| `sales_team.group_sale_salesman` (Sales / Own Documents Only) | read-only, restricted to recognition lines linked to SOs where `salesman_id == user` (via a parallel record rule mirroring Odoo 19's pattern on `sale.order.line`) |
| `sales_team.group_sale_salesman_all_leads` (Sales / All Documents) | read-only, all recognition lines |

A multi-company `ir.rule` on `x.revenue.recognition.line` enforces
`company_id in company_ids` for every user. There are no extra ACLs on
the recognition `account.move` itself — existing accounting rules apply
unchanged.

## Tests

The module ships with 22 unit tests covering invoice routing, recognition
triggers, partial deliveries / backorders, returns, credit notes,
idempotency, invoice reset reversal, multi-currency (frozen invoice rate),
service handling (auto / on_invoice / on_delivery), tax separation,
multi-invoice allocation (FIFO), security (parallel record rule), and
dropship `sale_line_id` propagation.

Run them on a fresh test database:

```
odoo-bin -d test_db -i unearned_revenue_recognition --test-enable \
         --test-tags=unearned_revenue_recognition --stop-after-init
```

On Odoo.sh, tests run automatically during the staging-branch build.

## License

LGPL-3.

## Author / Maintainer

Novalyft Solutions.
