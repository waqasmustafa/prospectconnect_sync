# prospectconnect_sync/models/pc_user_mapping.py
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PcUserMapping(models.Model):
    _name = "pc.user.mapping"
    _description = "ProspectConnect User Mapping"
    _rec_name = "odoo_user_id"

    odoo_user_id = fields.Many2one("res.users", string="Odoo User", required=True)
    pc_user_id = fields.Char(string="ProspectConnect User ID", required=True)
    pc_user_name = fields.Char(string="ProspectConnect User Name")

    _sql_constraints = [
        ("pc_user_unique", "unique(pc_user_id)", "ProspectConnect User ID must be unique."),
    ]

    @api.model
    def fetch_from_api(self):
        """Fetch users from ProspectConnect and update mapping.

        NOTE: This is a stub. You will need to adjust the endpoint according
        to the official docs when you know the exact path for listing users/team members.
        """
        if not requests:
            raise UserError(_("Python 'requests' library not available."))

        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("prospectconnect_sync.api_key")
        base_url = icp.get_param("prospectconnect_sync.base_url", "https://api.prospectconnect.ai")

        if not api_key:
            raise UserError(_("Please configure API key in settings first."))

        # TODO: replace this with the real users endpoint when known
        url = base_url.rstrip("/") + "/team/listUsers"
        headers = {
            "Accept": "application/json",
            "Authorization": api_key,
        }

        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:  # pragma: no cover
            _logger.exception("Error fetching ProspectConnect users")
            raise UserError(_("Error fetching users from ProspectConnect: %s") % e)

        # Expected shape: {"data": [{"id": "...", "name": "...", "email": "..."}]}
        items = data.get("data") or []
        for item in items:
            pc_user_id = item.get("id")
            name = item.get("name") or item.get("email") or pc_user_id
            if not pc_user_id:
                continue

            mapping = self.search([("pc_user_id", "=", pc_user_id)], limit=1)
            if not mapping:
                mapping = self.create(
                    {
                        "pc_user_id": pc_user_id,
                        "pc_user_name": name,
                        # odoo_user_id left empty for manual assignment
                    }
                )
            else:
                mapping.pc_user_name = name
