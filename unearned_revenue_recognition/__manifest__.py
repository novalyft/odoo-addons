{
    "name": "Unearned Revenue Recognition on Delivery",
    "version": "19.0.1.0.1",
    "category": "Accounting/Accounting",
    "summary": "Defer revenue recognition from invoice posting to physical delivery (IFRS 15 / ASC 606).",
    "description": """
Unearned Revenue Recognition on Delivery
========================================

Generic, reusable Odoo 19 module that defers revenue recognition from invoice
posting to physical delivery in line with IFRS 15 / ASC 606. Customers are
invoiced upfront for AR / payment tracking, but the credit side is routed to
an Unearned Revenue liability account. Revenue is moved from Unearned Revenue
to Sales Revenue automatically when the corresponding stock picking is
validated. Returns post the inverse entry; invoice cancellation reverses the
recognition.

VAT recognition remains on the invoice (correct per most tax-point rules,
including the Lebanese / GCC pattern). Only the revenue side is deferred.

Compatible with both Odoo 19 Community and Enterprise. The native
Enterprise Deferred Revenue Account is detected at runtime and used as the
third step of the deferral-account fallback chain when account_accountant
is installed; otherwise the module silently skips that step.
    """,
    "author": "Novalyft Solutions",
    "maintainer": "Novalyft Solutions",
    "website": "https://novalyftsolutions.com",
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
    "installable": True,
    "application": False,
    "auto_install": False,
}
