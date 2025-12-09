# ProspectConnect / Centripe Sync for Odoo 18

Complete bi-directional synchronization between Odoo 18 and ProspectConnect (Centripe) CRM.

## Features

### ✅ Bi-directional Sync
- **Contacts/Customers**: Full details including names, emails, phones, company, address, country, tags, lead source, assignee, and timestamps
- **Opportunities/Deals**: Name, pipeline/stage mapping, value, status, linked contact, assignee, notes, and timestamps
- **Tasks/Activities**: Title, description, related contact/deal, assignee, due date, and completion status
- **Notes/Comments**: Sync as internal notes in both systems

### ✅ Field Syncing
- **Assigned To** field (owner/user) syncs both directions for Contacts, Opportunities, and Tasks
- **Tags** and **Lead Source** fields correctly mapped and synced
- **Country** field included in all relevant records
- **Pipeline/Stage** mapping for opportunities

### ✅ Data Integrity & Performance
- **No duplicate records**: Uses ProspectConnect IDs in Odoo custom fields to match records
- **Timestamp-based conflict resolution**: Last updated record takes precedence
- **Fast updates**: Optimized for quick sync (goal: under 10 seconds)
- **Robust error handling**: Retry mechanism for failed syncs with detailed error logging

### ✅ Periodic Check & Sync Configuration
- **Daily automatic reconciliation** at 2 AM to detect and fix missed syncs
- **Configurable sync direction**: Odoo → ProspectConnect, ProspectConnect → Odoo, or Bi-directional
- **Configurable schedule**: Adjustable polling interval (default: 5 minutes)
- **Manual sync**: Trigger immediate sync from settings

## Installation

1. Copy the `prospectconnect_sync` folder to your Odoo addons directory
2. Restart Odoo server
3. Update Apps List (Settings → Apps → Update Apps List)
4. Search for "ProspectConnect" and click Install

## Configuration

### 1. API Configuration

Go to **ProspectConnect → Configuration → Settings**

1. Enter your **ProspectConnect API Key**
2. Verify the **Base URL** (default: https://api.prospectconnect.ai)
3. Click **Test Connection** to verify

### 2. Sync Behavior

Configure how sync works:

- **Sync Direction**: Choose between:
  - Odoo → ProspectConnect (one-way push)
  - ProspectConnect → Odoo (one-way pull)
  - Bi-directional (recommended)

- **Trigger Mode**: Choose when to sync from Odoo:
  - On Create
  - On Update
  - On Create/Update (recommended)

### 3. What To Sync

Enable/disable sync for each record type:
- ☑ Contacts
- ☑ Opportunities
- ☑ Tasks
- ☑ Notes

### 4. User Mapping

Map Odoo users to ProspectConnect users:

1. Go to **ProspectConnect → Configuration → User Mapping**
2. Click **Fetch Users** button in settings to import ProspectConnect users
3. Manually map each ProspectConnect user to an Odoo user

### 5. Pipeline Mapping

Map Odoo CRM stages to ProspectConnect pipelines:

1. Go to **ProspectConnect → Configuration → Pipeline Mapping**
2. Click **Fetch Pipelines** button in settings to import ProspectConnect pipelines
3. Manually map each ProspectConnect stage to an Odoo CRM stage

### 6. Enable Cron Jobs

1. Go to **Settings → Technical → Automation → Scheduled Actions**
2. Find "ProspectConnect Incremental Sync" and activate it
3. Find "ProspectConnect Nightly Reconciliation" and activate it

## Usage

### Manual Sync

Click **Sync Now** button in settings to trigger immediate sync.

### Automatic Sync

Once configured and cron jobs are enabled:
- **Incremental sync** runs every 5 minutes (configurable)
- **Nightly reconciliation** runs at 2 AM daily

### Monitor Sync Jobs

Go to **ProspectConnect → Sync Jobs** to view:
- Pending jobs
- Failed jobs with error messages
- Completed jobs
- Retry counts

## Synced Fields Reference

### Contacts (res.partner)
| Odoo Field | ProspectConnect Field | Direction |
|------------|----------------------|-----------|
| Name | name, firstName, lastName | ↔ |
| Email | email | ↔ |
| Phone | phone | ↔ |
| Mobile | phone (fallback) | → |
| Street | address1 | ↔ |
| City | city | ↔ |
| State | state | ↔ |
| ZIP | postalCode | ↔ |
| Country | country.country_code, country.name | ↔ |
| Tags | tags | ↔ |
| Lead Source | source | ↔ |
| Assigned To | assignedTo | ↔ |

### Opportunities (crm.lead)
| Odoo Field | ProspectConnect Field | Direction |
|------------|----------------------|-----------|
| Name | name | ↔ |
| Expected Revenue | value | ↔ |
| Status | status | ↔ |
| Stage | stageId | ↔ |
| Pipeline | pipelineId | ↔ |
| Contact | contactId | ↔ |
| Assigned To | assignedTo | ↔ |
| Description | notes | ↔ |

### Tasks (mail.activity)
| Odoo Field | ProspectConnect Field | Direction |
|------------|----------------------|-----------|
| Summary | name | ↔ |
| Note | description | ↔ |
| Due Date | due_date, due_time | ↔ |
| Assigned To | assignedTo | ↔ |
| State | completed | ↔ |
| Related Contact | contact_ids | ↔ |
| Related Deal | deal_ids | ↔ |

### Notes (mail.message)
| Odoo Field | ProspectConnect Field | Direction |
|------------|----------------------|-----------|
| Body | body | ↔ |
| Related Contact | contactId | ↔ |
| Related Deal | dealId | ↔ |

## Troubleshooting

### Connection Test Fails
- Verify API key is correct
- Check base URL is accessible
- Ensure `requests` Python library is installed

### Records Not Syncing
- Check sync direction in settings
- Verify the record type is enabled in "What To Sync"
- Check cron jobs are active
- Review Sync Jobs for error messages

### Duplicate Records
- Ensure ProspectConnect IDs are properly stored
- Run nightly reconciliation manually
- Check for manual record creation in both systems

### Field Not Syncing
- Verify user/pipeline mapping is complete
- Check field has a value in source system
- Review sync job error messages

## API Endpoints Used

This module uses the following ProspectConnect API endpoints:

**Contacts:**
- `POST /contact/upsert` - Create/update contact
- `GET /contacts/list` - List contacts

**Deals:**
- `POST /deal/create` - Create deal
- `POST /deal/update` - Update deal
- `GET /deals/list` - List deals

**Tasks:**
- `POST /task/addTask` - Create task
- `POST /task/updateTaskById` - Update task
- `GET /tasks/list` - List tasks

**Notes:**
- `POST /note/create` - Create note
- `GET /notes/list` - List notes

**Metadata:**
- `GET /team/listUsers` - List users
- `GET /deal/pipelines` - List pipelines and stages

> **Note**: Some endpoints may need adjustment based on the actual ProspectConnect API documentation at https://prospectconnect.stoplight.io/docs/prospectconnect/

## Support

For issues, questions, or feature requests:
- **Email**: mustafawaqas0@gmail.com
- **LinkedIn**: https://www.linkedin.com/in/waqas-mustafa-ba5701209/

## License

LGPL-3

## Credits

Developed by Waqas Mustafa
