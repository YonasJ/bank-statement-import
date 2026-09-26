from odoo import _, fields, models


class PlaidAccountSelectorWizard(models.TransientModel):
    _name = "plaid.account.selector.wizard"
    _description = "Select Plaid Account"

    provider_id = fields.Many2one(
        "online.bank.statement.provider", required=True, readonly=True
    )
    line_ids = fields.One2many(
        "plaid.account.selector.line",
        "wizard_id",
        string="Available Accounts",
    )


class PlaidAccountSelectorLine(models.TransientModel):
    _name = "plaid.account.selector.line"
    _description = "Plaid Account Selector Line"

    wizard_id = fields.Many2one("plaid.account.selector.wizard", ondelete="cascade")
    account_id = fields.Char("Account ID", required=True, readonly=True)
    name = fields.Char("Account Name", readonly=True)
    official_name = fields.Char("Official Name", readonly=True)
    mask = fields.Char("Mask (Last Digits)", readonly=True)
    type = fields.Char("Type", readonly=True)
    subtype = fields.Char("Subtype", readonly=True)
    currency = fields.Char("Currency", readonly=True)

    def action_select(self):
        self.ensure_one()
        provider = self.wizard_id.provider_id
        provider.write(
            {
                "plaid_account_id": self.account_id,
                "plaid_account_name": self.name,
                "plaid_account_mask": self.mask,
                "plaid_account_currency": self.currency,
            }
        )
        provider.message_post(
            body=_(
                "Plaid account linked: <b>%(name)s</b> (Mask: %(mask)s, Currency: %(currency)s, ID: %(account_id)s)"
            )
            % {
                "name": self.name or "N/A",
                "mask": self.mask or "N/A",
                "currency": self.currency or "N/A",
                "account_id": self.account_id,
            }
        )
        return {"type": "ir.actions.act_window_close"}
