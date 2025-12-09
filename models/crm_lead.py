# prospectconnect_sync/models/crm_lead.py
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    pc_deal_id = fields.Char(string="ProspectConnect Deal ID", index=True)
    pc_last_sync_at = fields.Datetime(string="PC Deal Last Sync At")
    pc_last_remote_update = fields.Datetime(
        string="PC Deal Last Remote Update",
        help="Timestamp of last update from ProspectConnect (for conflict resolution)"
    )
    pc_remote_assignee_id = fields.Char(
        string="PC Assignee ID",
        help="ProspectConnect user ID of the assignee"
    )
    pc_remote_stage_id = fields.Char(
        string="PC Stage ID",
        help="ProspectConnect stage ID"
    )
    pc_remote_pipeline_id = fields.Char(
        string="PC Pipeline ID",
        help="ProspectConnect pipeline ID"
    )

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._pc_maybe_sync_to_pc(trigger="on_create")
        return leads

    def write(self, vals):
        res = super().write(vals)
        self._pc_maybe_sync_to_pc(trigger="on_update")
        return res

    def _pc_maybe_sync_to_pc(self, trigger):
        """Schedule sync jobs for deals/opportunities."""
        config = self.env["ir.config_parameter"].sudo()
        if not config.get_param("prospectconnect_sync.sync_deals", "False") == "True":
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

        for lead in self.filtered(lambda l: l.type == "opportunity"):
            self.env["pc.sync.job"].sudo().create(
                {
                    "direction": "odoo_to_pc",
                    "object_type": "deal",
                    "odoo_model": lead._name,
                    "odoo_res_id": lead.id,
                }
            )
            _logger.debug(
                "ProspectConnect: queued sync job for deal %s (%s)",
                lead.id,
                lead.name,
            )

