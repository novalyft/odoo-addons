from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # TYPE: addition
    x_default_unearned_revenue_account_id = fields.Many2one(
        related="company_id.x_default_unearned_revenue_account_id",
        readonly=False,
    )
    x_recognition_journal_id = fields.Many2one(
        related="company_id.x_recognition_journal_id",
        readonly=False,
    )
