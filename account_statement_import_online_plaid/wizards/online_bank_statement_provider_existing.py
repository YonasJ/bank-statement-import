from odoo import _, fields, models
from odoo.exceptions import UserError


class OnlineBankStatementProviderExistingPlaid(models.TransientModel):
    _name = "online.bank.statement.provider.existing.plaid"
    _description = "Reuse Existing Plaid Connection"

    provider_id = fields.Many2one(
        "online.bank.statement.provider", required=True, readonly=True
    )
    other_provider_id = fields.Many2one(
        "online.bank.statement.provider",
        string="Existing Plaid Connection",
        required=True,
        domain="[('service', '=', 'plaid'), ('plaid_access_token', '!=', False), ('id', '!=', provider_id)]",
    )

    def action_link_and_select(self):
        self.ensure_one()
        provider = self.provider_id
        other = self.other_provider_id
        if not other.plaid_access_token:
            raise UserError(_("The selected provider does not have an active Plaid connection."))
        provider.write(
            {
                "username": other.username,
                "password": other.password,
                "plaid_host": other.plaid_host,
                "plaid_access_token": other.plaid_access_token,
            }
        )
        provider.message_post(
            body=_("Reused Plaid credentials and connection from <b>%(name)s</b>.")
            % {"name": other.name}
        )
        # Try auto-matching first
        matched = provider._auto_match_plaid_account()
        if matched and provider.plaid_account_id:
            return {"type": "ir.actions.act_window_close"}
        # If not matched or ambiguous, open account selector wizard
        return provider.action_select_plaid_account()
