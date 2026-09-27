/** @odoo-module **/
/* global Plaid */
import {registry} from "@web/core/registry";

export async function plaid_login(env, action) {
    const handler = Plaid.create({
        onSuccess: async (public_token) => {
            await env.services.orm.call(action.params.call_model, action.params.call_method, [
                public_token,
                action.params.object_id,
            ]);
            if (action.params.call_model === "plaid.bank.connection") {
                env.services.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "plaid.bank.connection",
                    res_id: action.params.object_id,
                    views: [[false, "form"]],
                    target: "current",
                });
            } else {
                env.services.action.doAction({
                    type: "ir.actions.client",
                    tag: "reload",
                });
            }
        },

        token: action.params.token,
    });
    handler.open();
}

registry.category("actions").add("plaid_login", plaid_login);
