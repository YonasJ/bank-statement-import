# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class PlaidBankAccount(models.Model):
    _name = "plaid.bank.account"
    _description = "Plaid Bank Account"
    _order = "name, mask"

    connection_id = fields.Many2one(
        "plaid.bank.connection",
        string="Bank Connection",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="connection_id.company_id",
        store=True,
        readonly=True,
    )
    name = fields.Char(string="Account Name", required=True)
    plaid_account_id = fields.Char(string="Plaid Account ID", required=True, index=True)
    mask = fields.Char(string="Account Mask (Last 4)")
    account_type = fields.Char(string="Type")
    subtype = fields.Char(string="Subtype")
    currency_code = fields.Char(string="Currency")
    display_name = fields.Char(
        compute="_compute_display_name", store=True, index=True
    )
    provider_ids = fields.One2many(
        "online.bank.statement.provider",
        "plaid_bank_account_id",
        string="Linked Statement Providers",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Linked Journal",
        compute="_compute_journal_id",
        inverse="_inverse_journal_id",
        domain="[('type', '=', 'bank')]",
    )

    @api.depends("provider_ids.journal_id")
    def _compute_journal_id(self):
        for rec in self:
            rec.journal_id = rec.provider_ids[:1].journal_id

    def _inverse_journal_id(self):
        Provider = self.env["online.bank.statement.provider"]
        for rec in self:
            current_provider = rec.provider_ids[:1]
            if rec.journal_id:
                provider = Provider.search([("journal_id", "=", rec.journal_id.id)], limit=1)
                if not provider:
                    provider = Provider.create({
                        "name": f"{rec.journal_id.name} plaid",
                        "journal_id": rec.journal_id.id,
                        "service": "plaid",
                        "plaid_connection_id": rec.connection_id.id,
                        "plaid_bank_account_id": rec.id,
                    })
                else:
                    provider.write({
                        "service": "plaid",
                        "plaid_connection_id": rec.connection_id.id,
                        "plaid_bank_account_id": rec.id,
                    })
                rec.journal_id.bank_statements_source = "online"
                rec.journal_id.online_bank_statement_provider = "plaid"
            elif current_provider:
                current_provider.write({"plaid_bank_account_id": False})

    @api.depends("name", "mask", "currency_code", "connection_id.name")
    def _compute_display_name(self):
        for rec in self:
            mask_str = f" (...{rec.mask})" if rec.mask else ""
            curr_str = f" [{rec.currency_code}]" if rec.currency_code else ""
            conn_str = f"{rec.connection_id.name} - " if rec.connection_id else ""
            rec.display_name = f"{conn_str}{rec.name}{mask_str}{curr_str}"
