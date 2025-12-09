# prospectconnect_sync/models/res_partner.py
import logging

from odoo import api, fields, models, _
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    pc_contact_id = fields.Char(string="ProspectConnect Contact ID", index=True)
    pc_last_sync_at = fields.Datetime(string="PC Last Sync At")
    pc_last_remote_update = fields.Datetime(
        string="PC Last Remote Update",
        help="Timestamp of last update from ProspectConnect (for conflict resolution)"
    )
    pc_lead_source = fields.Char(
        string="Lead Source",
        help="Source of the lead (e.g., Website, Referral, etc.)"
    )
    pc_assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        help="User assigned to this contact in ProspectConnect"
    )
    pc_remote_assignee_id = fields.Char(
        string="PC Assignee ID",
        help="ProspectConnect user ID of the assignee"
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._pc_maybe_sync_to_pc(trigger="on_create")
        return partners

    def write(self, vals):
        res = super().write(vals)
        self._pc_maybe_sync_to_pc(trigger="on_update")
        return res

    # --- Sync helpers (structure only, actual API handled in pc_sync_job) ---

    def _pc_maybe_sync_to_pc(self, trigger):
        """Schedule sync jobs for records when config allows it."""
        config = self.env["ir.config_parameter"].sudo()
        if not config.get_param("prospectconnect_sync.sync_contacts", "True") == "True":
            return

        trigger_mode = config.get_param(
            "prospectconnect_sync.trigger_mode", "on_create_update"
        )
        if trigger_mode == "on_create" and trigger != "on_create":
            return
        if trigger_mode == "on_update" and trigger != "on_update":
            return

        direction = config.get_param(
            "prospectconnect_sync.sync_direction", "bidirectional"
        )
        if direction not in ("odoo_to_pc", "bidirectional"):
            return

        for partner in self:
            self.env["pc.sync.job"].sudo().create(
                {
                    "direction": "odoo_to_pc",
                    "object_type": "contact",
                    "odoo_model": partner._name,
                    "odoo_res_id": partner.id,
                }
            )
            _logger.debug(
                "ProspectConnect: queued sync job for partner %s (%s)",
                partner.id,
                html_escape(partner.display_name),
            )

