{
    "name": "ProspectConnect / Centripe Sync",
    "version": "18.0.2.0.0",
    "summary": "Complete bi-directional sync between Odoo 18 and ProspectConnect (Centripe) - Contacts, Deals, Tasks, Notes with field mapping and conflict resolution.",
    "description": """
ProspectConnect / Centripe Sync
================================

Features:
---------
* **Bi-directional sync** for Contacts, Opportunities, Tasks, and Notes
* **Real-time updates** with configurable triggers (on create/update)
* **Field mapping** including assignee, lead source, tags, country, pipeline/stage
* **User and Pipeline mapping** for seamless data synchronization
* **Conflict resolution** based on timestamps
* **Duplicate prevention** using ProspectConnect IDs
* **Incremental sync** every 5 minutes (configurable)
* **Nightly reconciliation** at 2 AM for data integrity
* **Robust error handling** with retry mechanism
* **Sync job monitoring** with detailed status tracking

Synced Fields:
--------------
**Contacts:**
- Full name, email, phone, mobile
- Address (street, city, state, postal code, country)
- Tags, Lead Source, Assigned To
- Timestamps for conflict resolution

**Opportunities/Deals:**
- Name, value, status, probability
- Pipeline and stage mapping
- Linked contact, assigned to
- Notes and timestamps

**Tasks/Activities:**
- Title, description, due date
- Linked contact/deal, assigned to
- Completion status

**Notes:**
- Internal notes on contacts and opportunities
- Automatic sync of comments
    """,
    "category": "CRM",
    "author": "Waqas Mustafa",
    "website": "https://www.linkedin.com/in/waqas-mustafa-ba5701209/",
    "support": "mustafawaqas0@gmail.com",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "crm", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/pc_menus.xml",
        "views/pc_settings_view.xml",
        "views/pc_user_mapping_views.xml",
        "views/pc_pipeline_mapping_views.xml",
        "views/pc_task_mapping_views.xml",
        "data/pc_cron_jobs.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}

