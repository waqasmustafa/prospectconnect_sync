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

        # Hypothesis based on pipeline pattern: GET /user/getUserList
        # and response structure from screenshot (users array, _id field)
        url = base_url.rstrip("/") + "/user/getUserList"
        headers = {
            "Accept": "application/json",
            "Authorization": api_key,
        }

        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 404:
                # Fallback or just log warning
                _logger.warning("ProspectConnect '/user/getUserList' not found (404).")
                return
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            _logger.warning("Error fetching ProspectConnect users: %s", e)
            return

        # Expected shape based on screenshot: {"users": [{"_id": "...", "first_name": "...", ...}]}
        # Or maybe {"data": ...} - we'll try both
        items = data.get("users") or data.get("data") or []
        
        for item in items:
            pc_user_id = item.get("_id") or item.get("id")
            if not pc_user_id:
                continue
                
            # Construct name
            first = item.get("first_name") or ""
            last = item.get("last_name") or ""
            name = f"{first} {last}".strip() or item.get("name") or item.get("email") or pc_user_id
            
            mapping = self.search([("pc_user_id", "=", pc_user_id)], limit=1)
            vals = {
                "pc_user_id": pc_user_id,
                "pc_user_name": name,
            }
            if mapping:
                mapping.write(vals)
            else:
                self.create(vals)
