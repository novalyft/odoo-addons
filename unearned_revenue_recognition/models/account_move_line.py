from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # TYPE: addition
    x_target_revenue_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Target Revenue Account",
        copy=False,
        help="The standard income account where revenue will eventually land when this invoice "
             "line is recognized via delivery. Captured at invoice line creation time so the "
             "recognition target is frozen against later product reconfiguration.",
    )

    # TYPE: behavioral_change
    def _compute_account_id(self):
        """Defensive override: after super computes account_id, restore the deferral account
        on lines where revenue should be deferred.

        Background: the base compute (account/models/account_move_line.py:577) assigns
        accounts['income'] to line.account_id for product invoice lines on sale documents.
        Although our _prepare_invoice_line override supplies account_id directly in create
        vals and precompute honors that, this guard recovers from edge cases where the
        compute re-fires (e.g. product_id changed on an existing line, fiscal-position
        recomputation). We only act when x_target_revenue_account_id is set, indicating
        the line was originally routed through our redirect path.
        """
        super()._compute_account_id()
        for line in self:
            if not line.x_target_revenue_account_id:
                continue
            if not line.move_id.is_sale_document(include_receipts=True):
                continue
            if line.display_type and line.display_type != "product":
                continue
            if not line.product_id:
                continue
            # Only restore deferral on lines that were originally redirected
            # (i.e. the product still wants on-delivery recognition).
            if line.product_id.product_tmpl_id._get_effective_revenue_method() != "on_delivery":
                continue
            sale_line = line.sale_line_ids[:1]
            if not sale_line:
                continue
            deferral = sale_line._get_unearned_revenue_account(line.product_id)
            if not deferral:
                continue
            # Only redirect if the compute reverted us to the standard income account.
            if line.account_id == line.x_target_revenue_account_id:
                line.account_id = deferral
