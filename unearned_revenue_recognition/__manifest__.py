{
    "name": "Unearned Revenue Recognition on Delivery (IFRS 15 / ASC 606)",
    "version": "19.0.1.1.0",
    "category": "Accounting/Accounting",
    "summary": (
        "Defer revenue recognition to delivery — IFRS 15 / ASC 606 compliance for "
        "retail, e-commerce, and prepayment workflows. Unearned revenue, deferred "
        "revenue, returns, credit notes, multi-currency, multi-company."
    ),
    "description": """
Unearned Revenue Recognition on Delivery — IFRS 15 / ASC 606
=============================================================

Defer revenue recognition from invoice posting to physical delivery, in line
with IFRS 15 and ASC 606. Built for retail, e-commerce, wholesale, and any
business that invoices customers upfront but delivers goods later.

Why this module
---------------
* Customers pay 100% at checkout — accounting needs to invoice for AR / cash
  tracking, but recognizing revenue on the P&L too early violates IFRS 15 /
  ASC 606 because the performance obligation has not been satisfied.
* Standard Odoo recognizes revenue at invoice posting; this module routes
  the credit side to an Unearned Revenue liability account instead.
* When the corresponding stock picking is validated, an automatic
  Miscellaneous journal entry moves the delivered portion from Unearned
  Revenue to Sales Revenue.
* Returns post the inverse entry automatically. Invoice cancellation
  reverses recognition. Credit notes inherit the deferral account, so
  order modifications never leak to the P&L.
* VAT is recognized on the invoice (correct per most tax-point rules
  including the Lebanese and GCC patterns). Only the revenue side defers.

Highlights
----------
* Three-level deferral-account fallback chain: product category →
  company default → Odoo Enterprise's native Deferred Revenue Account.
* Partial deliveries and backorders recognize only their share.
* Multi-currency: recognition uses the invoice's frozen FX rate.
* Multi-company: per-company books with a multi-company ir.rule.
* Full audit trail via the dedicated x.revenue.recognition.line model.
* Smart buttons on Sales Order, Customer Invoice, and Stock Picking forms.
* Sales Order header shows Recognized Revenue / Pending Recognition /
  Status (not_started / partial / complete).
* New report under Accounting → Reporting → Deferred Revenue.
* Parallel mirrored record rule for "Own Documents Only" salesmen.
* 22 unit tests covering all edge cases.
* Compatible with Odoo 19 Community and Enterprise.

Keywords
--------
Revenue recognition, deferred revenue, unearned revenue, IFRS 15, ASC 606,
GAAP, accrual accounting, prepayment, advance payment, delivery-based
revenue, retail accounting, e-commerce accounting, performance obligation,
multi-currency, multi-company, Odoo 19, Lebanon, GCC.
    """,
    "author": "Novalyft Solutions",
    "maintainer": "Novalyft Solutions",
    "website": "https://novalyftsolutions.com",
    "support": "m.hassan@novalyftsolutions.com",
    "license": "LGPL-3",
    "depends": [
        "account",
        "sale_management",
        "stock",
        "sale_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "views/res_config_settings_views.xml",
        "views/product_category_views.xml",
        "views/product_template_views.xml",
        "views/revenue_recognition_line_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/stock_picking_views.xml",
        "views/menus.xml",
    ],
    "images": [
        # First entry doubles as the detail-page banner AND the card-cover
        # thumbnail. The _screenshot suffix is what the Apps Store cover slot
        # filters by — without it the cover falls through to the next image.
        "static/description/cover_screenshot.png",
        "static/description/sale_order_recognition_screenshot.png",
        "static/description/product_revenue_method_screenshot.png",
        "static/description/accounting_settings_screenshot.png",
        "static/description/product_category_screenshot.png",
    ],
    "price": 0.00,
    "currency": "USD",
    "installable": True,
    "application": False,
    "auto_install": False,
}
