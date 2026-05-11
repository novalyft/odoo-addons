{
    "name": "Unearned Revenue Recognition on Delivery",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Defer revenue recognition from invoice posting to physical delivery (IFRS 15 / ASC 606).",
    "description": """
Defers revenue recognition from invoice-posting time to physical-delivery time
in line with IFRS 15 / ASC 606. Customers are invoiced upfront for AR / payment
tracking, but the credit side is routed to an Unearned Revenue liability account.
Revenue is moved from Unearned Revenue to Sales Revenue automatically when the
corresponding stock picking is validated. Returns reverse the recognition.
VAT recognition remains on the invoice; only the revenue side is deferred.
    """,
    "author": "Novalyft Solutions",
    "maintainer": "Novalyft Solutions",
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
