# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PlaidBankConnection(models.Model):
    _name = "plaid.bank.connection"
    _description = "Plaid Bank Connection"
    _order = "name"

    name = fields.Char(
        string="Bank / Connection Name",
        required=True,
        default="New Bank Connection",
    )
    institution_id = fields.Char(string="Institution ID", readonly=True)
    institution_name = fields.Char(string="Institution Name", readonly=True)
    plaid_access_token = fields.Char(string="Access Token")
    plaid_item_id = fields.Char(string="Item ID", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Not Connected"),
            ("connected", "Connected"),
            ("error", "Re-authentication Required"),
        ],
        default="draft",
        string="Status",
        required=True,
    )
    account_ids = fields.One2many(
        "plaid.bank.account",
        "connection_id",
        string="Bank Accounts",
    )
    provider_ids = fields.One2many(
        "online.bank.statement.provider",
        "plaid_connection_id",
        string="Statement Providers",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    account_count = fields.Integer(compute="_compute_counts", string="Accounts Count")
    provider_count = fields.Integer(compute="_compute_counts", string="Providers Count")

    @api.depends("account_ids", "provider_ids")
    def _compute_counts(self):
        for rec in self:
            rec.account_count = len(rec.account_ids)
            rec.provider_count = len(rec.provider_ids)

    def _get_plaid_client(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        client_id = (
            ICP.get_param("account_statement_import_online_plaid.plaid_client_id")
            or self.company_id.plaid_client_id
            or ""
        )
        secret = (
            ICP.get_param("account_statement_import_online_plaid.plaid_secret")
            or self.company_id.plaid_secret
            or ""
        )
        host = (
            ICP.get_param("account_statement_import_online_plaid.plaid_host")
            or self.company_id.plaid_host
            or "sandbox"
        )
        if not client_id or not secret:
            raise UserError(
                _(
                    "Plaid Client ID or Secret Key not found. Please configure them in Accounting Settings."
                )
            )
        return self.env["plaid.interface"]._client(client_id, secret, host)

    @api.model
    def action_connect_new_bank(self, *args, **kwargs):
        connection = self.create({"name": "New Bank Connection"})
        return connection.action_connect_plaid()

    def action_connect_plaid(self):
        self.ensure_one()
        client = self._get_plaid_client()
        lang = (
            self.env["res.lang"]._lang_get(self.env.lang or self.env.user.lang).iso_code
        )
        country_code = (self.company_id.country_id.code or "US").upper()
        if country_code not in ["US", "CA", "GB", "FR", "ES", "IE", "NL", "DE"]:
            country_code = "US"
        company_name = self.company_id.name or "Odoo"
        link_token = self.env["plaid.interface"]._link(
            client, lang, country_code, company_name, ["transactions"]
        )
        return {
            "type": "ir.actions.client",
            "tag": "plaid_login",
            "params": {
                "call_model": "plaid.bank.connection",
                "call_method": "plaid_create_access_token",
                "object_id": self.id,
                "token": link_token,
            },
        }

    def action_update_credentials(self):
        self.ensure_one()
        if not self.plaid_access_token:
            raise UserError(_("No access token found to update. Connect bank first."))
        client = self._get_plaid_client()
        lang = (
            self.env["res.lang"]._lang_get(self.env.lang or self.env.user.lang).iso_code
        )
        country_code = (self.company_id.country_id.code or "US").upper()
        if country_code not in ["US", "CA", "GB", "FR", "ES", "IE", "NL", "DE"]:
            country_code = "US"
        company_name = self.company_id.name or "Odoo"
        link_token = self.env["plaid.interface"]._link(
            client,
            lang,
            country_code,
            company_name,
            [],
            access_token=self.plaid_access_token,
        )
        return {
            "type": "ir.actions.client",
            "tag": "plaid_login",
            "params": {
                "call_model": "plaid.bank.connection",
                "call_method": "plaid_update_access_token",
                "object_id": self.id,
                "token": link_token,
            },
        }

    @api.model
    def plaid_create_access_token(self, public_token, active_id):
        connection = self.browse(active_id)
        if public_token:
            client = connection._get_plaid_client()
            plaid_interface = self.env["plaid.interface"]
            exchange = plaid_interface._exchange_public_token(client, public_token)
            connection.plaid_access_token = exchange["access_token"]
            connection.plaid_item_id = exchange.get("item_id")
            connection.state = "connected"

            try:
                item = plaid_interface._get_item(client, connection.plaid_access_token)
                inst_id = item.get("institution_id")
                connection.institution_id = inst_id
                if inst_id:
                    inst_name = plaid_interface._get_institution_name(client, inst_id)
                    if inst_name:
                        connection.institution_name = inst_name
                        if not connection.name or connection.name in [
                            "New",
                            "New Bank Connection",
                        ]:
                            connection.name = inst_name
            except Exception:
                pass

            connection.action_fetch_accounts()
        return True

    @api.model
    def plaid_update_access_token(self, public_token, active_id):
        connection = self.browse(active_id)
        connection.state = "connected"
        connection.action_fetch_accounts()
        return True

    def action_fetch_accounts(self):
        self.ensure_one()
        if not self.plaid_access_token:
            raise UserError(_("Please connect this bank with Plaid first."))
        client = self._get_plaid_client()
        accounts_data = self.env["plaid.interface"]._get_accounts(
            client, self.plaid_access_token
        )
        existing = {acc.plaid_account_id: acc for acc in self.account_ids}
        for acc in accounts_data:
            acc_id = acc.get("account_id")
            name = acc.get("name") or "Account"
            mask = acc.get("mask") or ""
            acc_type = str(acc.get("type") or "")
            subtype = str(acc.get("subtype") or "")
            currency_code = (
                acc.get("balances", {}).get("iso_currency_code")
                or acc.get("balances", {}).get("unofficial_currency_code")
                or ""
            )
            vals = {
                "connection_id": self.id,
                "plaid_account_id": acc_id,
                "name": name,
                "mask": mask,
                "account_type": acc_type,
                "subtype": subtype,
                "currency_code": currency_code,
            }
            if acc_id in existing:
                existing[acc_id].write(vals)
            else:
                self.env["plaid.bank.account"].create(vals)

    def action_view_providers(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account_statement_import_online.online_bank_statement_provider_action"
        )
        action["domain"] = [("plaid_connection_id", "=", self.id)]
        action["context"] = {
            "default_plaid_connection_id": self.id,
            "default_service": "plaid",
        }
        return action
