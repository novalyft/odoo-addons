from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # TYPE: addition
    x_default_unearned_revenue_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default Unearned Revenue Account",
        domain="[('account_type', '=', 'liability_current'), ('deprecated', '=', False)]",
        help="Liability account used by default for unearned revenue when no override is set "
             "on the product category. Acts as the second step of the deferral account fallback "
             "chain (after product category, before the native Enterprise deferred revenue setting).",
    )
    x_recognition_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Revenue Recognition Journal",
        domain="[('type', '=', 'general')]",
        help="Miscellaneous journal used to post revenue-recognition entries when goods are "
             "delivered. If empty, the first general journal of the company is used.",
    )
