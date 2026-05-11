from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_recognized_quantity(self):
        """Return net recognized quantity for this stock.move (in the SO line's UoM).

        - TYPE: addition
        Net = sum(non-reversal qty) - sum(reversal qty). Used by the picking-level
        recognition trigger to compute the delta still to recognize, ensuring
        idempotency across re-validations and backorders.
        """
        self.ensure_one()
        Recognition = self.env["x.revenue.recognition.line"]
        non_reversal = sum(
            Recognition.search([
                ("move_id", "=", self.id),
                ("is_reversal", "=", False),
            ]).mapped("quantity")
        )
        reversal = sum(
            Recognition.search([
                ("move_id", "=", self.id),
                ("is_reversal", "=", True),
            ]).mapped("quantity")
        )
        return non_reversal - reversal
