# Unearned Revenue Recognition on Delivery

Defers revenue recognition from invoice posting to physical delivery in
line with IFRS 15 / ASC 606. Built for retail / e-commerce scenarios where
the customer pays upfront but goods are delivered later — sometimes in
multiple shipments.

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

VAT is still recognized at invoice posting (correct per most tax-point
rules including the Lebanese / GCC pattern). Only the revenue side
is deferred.

## Installation

1. Drop `unearned_revenue_recognition/` into an Odoo 19 addons path.
2. Restart the Odoo server with the addons path including the new folder:
   `./odoo-bin -d <db> --addons-path=...,/path/to/odoo-custom-addon -u all`
3. From the apps screen, search for "Unearned Revenue Recognition" and install.
   The module depends on `account`, `sale_management`, `stock`, `sale_stock`.

The module is compatible with **Odoo 19 Community and Enterprise**. If the
Enterprise `account_accountant` module is installed, its native Deferred
Revenue Account is used as the third step of the deferral-account fallback
chain; otherwise that step is skipped silently.

## Configuration

After install, configure these in order of granularity (each level overrides
the broader one):

1. **Per product category** (recommended for most setups).
   Navigate to `Inventory → Configuration → Product Categories` (or open any
   category form). The new field **Unearned Revenue Account** sets the
   deferral target for every product in that category.

2. **Company default** (fallback for categories that leave the field empty).
   `Accounting → Configuration → Settings → Customer Invoices → Unearned
   Revenue Recognition`:
   - **Default Unearned Revenue Account** — the company-wide deferral target.
   - **Recognition Journal** — the Miscellaneous journal used to post the
     delivery-time recognition entries. Defaults to the first general journal.

3. **Per product** (advanced — override the auto behavior).
   On a product form's **Accounting** tab, **Revenue Recognition Method**:
   - **Automatic (default)** — goods recognize on delivery, services on invoice.
   - **Recognize on invoice posting** — never defer, even for goods.
   - **Recognize on delivery** — always defer, including for services.

### Fallback chain at invoice line creation

When invoicing a sale-order line whose product wants deferral, the deferral
account is resolved as:

1. `product.categ_id.x_unearned_revenue_account_id`
2. `company.x_default_unearned_revenue_account_id`
3. `company.deferred_revenue_account_id` (Odoo Enterprise's native setting; skipped if not installed)
4. Standard income account — a warning is added to the invoice chatter so
   the accountant knows the deferral did not take effect.

## Usage walkthrough

1. **Configure** the deferral account on the relevant category (or as
   company default).
2. **Create the sales order** as usual.
3. **Confirm and invoice** — the invoice posts and credits the **Unearned
   Revenue** account instead of Sales Revenue. AR and VAT post normally.
4. **Register payment** — books a normal AR-clearing entry.
5. **Validate the outgoing picking** — a new Misc-journal entry is posted
   automatically:
   ```
   Dr. Unearned Revenue   1000
       Cr. Sales Revenue        1000
   ```
   A line is recorded in `Accounting → Reporting → Revenue Recognition Lines`
   for the audit trail.
6. **Partial delivery / backorder** — each picking validates only the
   portion of revenue tied to its delivered quantity.
7. **Return** — validating an incoming return picking posts the inverse
   entry automatically.

The Sales Order, Customer Invoice, and Stock Picking forms each gain a
**Revenue Recognition** smart button that lists all recognition events
for that record.

## Reporting

- **Accounting → Reporting → Deferred Revenue** — lists posted invoice
  lines still parked in the deferral account, grouped by partner. Use this
  to monitor "billed but not delivered" balances.
- **Accounting → Reporting → Revenue Recognition Lines** — the full audit
  trail of recognition and reversal events.
- **Sales Order header badge** — `not_started / partial / complete` shows
  how much of the SO's revenue has been recognized.

## Known limitations

- **No time-based deferral.** This module recognizes on a discrete delivery
  event. For annual contracts, prepaid hours, or other time-spread revenue,
  use Odoo's native Enterprise Deferred Revenue feature instead.
- **Services with `on_delivery`.** When a service product is explicitly forced
  to `on_delivery` but has no downstream stock picking, the revenue stays
  parked in the Unearned Revenue account until you post a manual journal
  entry. The invoice chatter logs a warning in this case.
- **Manual invoices.** Invoices not originating from a sale order are not
  redirected even if their product would normally be deferred. Create
  manual recognition entries if needed.

## Reference: data flow

```
sale.order.line._prepare_invoice_line()        # set x_target_revenue_account_id + redirect account_id
        |
        v
account.move._post()                           # invoice posts, credits deferral
        |
        v
stock.picking._action_done()                   # outgoing: _recognize_revenue
        |                                      # incoming-return: _reverse_revenue_recognition
        v
account.move (recognition entry posted)
        |
        v
x.revenue.recognition.line (audit row)
```

Cancellation paths:

- `stock.picking.action_cancel` reverses recognition entries for that picking.
- `account.move.button_draft` / `button_cancel` reverses recognition entries
  for that invoice's lines.

## License

LGPL-3.

## Author

Novalyft Solutions.
