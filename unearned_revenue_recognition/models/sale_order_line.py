from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_unearned_revenue_account(self, product):
        """Resolve the deferral (Unearned Revenue) account for `product` on this SO line.

        - TYPE: addition
        Fallback chain (FR1):
            1. product.categ_id.x_unearned_revenue_account_id    (per-category override)
            2. company.x_default_unearned_revenue_account_id     (module's company default)
            3. company.deferred_revenue_account_id               (Odoo Enterprise native,
                                                                  account_accountant addon)
            4. None -> caller falls back to standard income account.

        Returns an account.account recordset (possibly empty).
        """
        if not product:
            return self.env["account.account"]
        company = self.company_id or self.order_id.company_id or self.env.company
        product = product.with_company(company)

        # Step 1: product category override (company_dependent field, so already scoped).
        if product.categ_id.x_unearned_revenue_account_id:
            return product.categ_id.x_unearned_revenue_account_id

        # Step 2: module's company default.
        if company.x_default_unearned_revenue_account_id:
            return company.x_default_unearned_revenue_account_id

        # Step 3: Enterprise native setting (runtime check so Community installs still work).
        native = getattr(company, "deferred_revenue_account_id", False)
        if native:
            return native

        return self.env["account.account"]

    # TYPE: behavioral_change
    def _prepare_invoice_line(self, **optional_values):
        """Generate invoice-line vals for this SO line, redirecting the revenue account
        to an Unearned Revenue (liability) account when the product's effective recognition
        method is 'on_delivery'.

        Standard behavior (sale/models/sale_order_line.py:1472) does NOT set account_id
        for regular product lines; it is computed later by account.move.line._compute_account_id
        from the product's income account chain. We post-super, then:
          1. Resolve the standard income account via the same chain Odoo uses
             (product_tmpl_id._get_product_accounts(fiscal_pos=...)['income']).
          2. Store that resolved income account in x_target_revenue_account_id so
             recognition has a stable target even if product config changes later.
          3. If the product's effective method is 'on_delivery' and a deferral account
             resolves via _get_unearned_revenue_account(), redirect account_id to
             the deferral account on the returned vals dict.

        Skipped for: display-only lines (section/note), combo lines, downpayment lines
        (the base method already pins account_id for those).
        """
        res = super()._prepare_invoice_line(**optional_values)

        # Skip non-product, display-only, or combo lines.
        if res.get("display_type") and res.get("display_type") != "product":
            return res
        if self.product_id.type == "combo":
            return res
        if self.is_downpayment:
            return res
        if not self.product_id:
            return res

        company = self.company_id or self.order_id.company_id or self.env.company
        fiscal_position = self.order_id.fiscal_position_id

        # Step 1: resolve the standard income account through Odoo's product->category->company chain.
        accounts = self.product_id.product_tmpl_id.with_company(company)._get_product_accounts()
        income_account = accounts.get("income")
        if fiscal_position and income_account:
            income_account = fiscal_position.map_account(income_account)

        # Step 2: record the target revenue account on the invoice line (always, when known).
        if income_account:
            res["x_target_revenue_account_id"] = income_account.id

        # Step 3: redirect account_id to deferral if recognition is deferred.
        method = self.product_id.product_tmpl_id._get_effective_revenue_method()
        if method == "on_delivery":
            deferral = self._get_unearned_revenue_account(self.product_id)
            if deferral:
                if fiscal_position:
                    deferral = fiscal_position.map_account(deferral)
                res["account_id"] = deferral.id
        return res
