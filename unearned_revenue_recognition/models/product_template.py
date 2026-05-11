from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # TYPE: addition
    x_revenue_recognition_method = fields.Selection(
        selection=[
            ("auto", "Automatic (based on product type)"),
            ("on_invoice", "Recognize on invoice posting"),
            ("on_delivery", "Recognize on delivery"),
        ],
        string="Revenue Recognition Method",
        default="auto",
        required=True,
        help="When the revenue tied to this product is recognized:\n"
             "- Automatic: services recognize on invoice, storable/consumable goods recognize on delivery.\n"
             "- On invoice posting: revenue hits the standard income account immediately.\n"
             "- On delivery: revenue is deferred to an Unearned Revenue account at invoice posting and "
             "moved to income when the related stock picking is validated.",
    )

    def _get_effective_revenue_method(self):
        """Return the effective recognition method ('on_invoice' or 'on_delivery') for this product.

        - TYPE: addition
        For 'auto', resolves based on Odoo 19's product.template.type enum:
          - 'consu' (Goods, storable and non-storable) -> 'on_delivery'
          - 'service' or 'combo' -> 'on_invoice'
        """
        self.ensure_one()
        if self.x_revenue_recognition_method == "auto":
            return "on_delivery" if self.type == "consu" else "on_invoice"
        return self.x_revenue_recognition_method
