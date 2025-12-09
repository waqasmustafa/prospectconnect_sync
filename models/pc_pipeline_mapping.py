# prospectconnect_sync/models/pc_pipeline_mapping.py
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PcPipelineMapping(models.Model):
    _name = "pc.pipeline.mapping"
    _description = "ProspectConnect Pipeline/Stage Mapping"
    _rec_name = "odoo_stage_id"

    odoo_stage_id = fields.Many2one(
        "crm.stage", string="Odoo Stage", required=True, ondelete="cascade"
    )
    pc_stage_id = fields.Char(string="ProspectConnect Stage ID", required=True)
    pc_stage_name = fields.Char(string="ProspectConnect Stage Name")
    pc_pipeline_id = fields.Char(string="ProspectConnect Pipeline ID")

    _sql_constraints = [
        ("pc_stage_unique", "unique(pc_stage_id)", "ProspectConnect Stage ID must be unique."),
    ]

    @api.model
    def fetch_from_api(self):
        """Fetch pipelines/stages from ProspectConnect.

        Endpoint verified: POST /deal/pipelines
        """
        if not requests:
            raise UserError(_("Python 'requests' library not available."))

        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("prospectconnect_sync.api_key")
        base_url = icp.get_param("prospectconnect_sync.base_url", "https://api.prospectconnect.ai")

        if not api_key:
            raise UserError(_("Please configure API key in settings first."))

        # Endpoint verified from docs: POST /deal/pipelines
        url = base_url.rstrip("/") + "/deal/pipelines"
        headers = {
            "Accept": "application/json",
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

        try:
            # Documentation says "Get Pipelines" is a POST request
            resp = requests.post(url, headers=headers, json={}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            _logger.exception("Error fetching ProspectConnect pipelines")
            raise UserError(_("Error fetching pipelines from ProspectConnect: %s") % e)

        # Expected structure: {"data": [{"id": "...", "stages": [...]}]}
        pipelines = data.get("data") or []
        for pipeline in pipelines:
            pipeline_id = pipeline.get("id")
            for stage in pipeline.get("stages") or []:
                pc_stage_id = stage.get("id")
                name = stage.get("name") or pc_stage_id
                if not pc_stage_id:
                    continue
                mapping = self.search([("pc_stage_id", "=", pc_stage_id)], limit=1)
                vals = {
                    "pc_stage_id": pc_stage_id,
                    "pc_stage_name": name,
                    "pc_pipeline_id": pipeline_id,
                }
                if mapping:
                    mapping.write(vals)
                else:
                    self.create(vals)
