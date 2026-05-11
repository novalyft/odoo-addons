from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    # TYPE: addition
    x_unearned_revenue_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Unearned Revenue Account",
        domain="[('account_type', '=', 'liability_current'), ('deprecated', '=', False)]",
        company_dependent=True,
        help="Liability account where revenue is parked at invoice posting for products in "
             "this category, until physical delivery moves it to the standard income account. "
             "When set, takes precedence over the company-level default and the native "
             "Enterprise deferred revenue setting.",
    )
