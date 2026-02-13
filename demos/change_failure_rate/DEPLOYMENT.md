# Change Failure Rate - Deployment Guide

## Prerequisites

- [x] Deployment Frequency function app already deployed
- [x] Azure SQL Database with `deployments` table
- [ ] GitHub App with Issues permission (need to add)
- [ ] SQL schema for `incidents` table

## Deployment Steps

### 1. Add GitHub App Permission

**Action Required:** Update GitHub App permissions

1. Go to: https://github.com/organizations/YOUR_ORG/settings/apps
2. Click on your GitHub App (e.g., "DORA Metrics Collector")
3. Navigate to: **Permissions & events**
4. Under **Repository permissions**, find **Issues**
5. Change from **No access** to **Read-only**
6. Click **Save changes**
7. **Important:** Organization admins will receive a notification to accept the permission change
8. Accept the permission update in: Organization Settings → GitHub Apps → Pending Requests

### 2. Create SQL Schema

**Option A: Azure Portal Query Editor (For EXISTING Deployments)**

1. Navigate to: Azure Portal → SQL Database → `sqldb-deployment-frequency`
2. Click **Query editor (preview)**
3. Authenticate with Azure Active Directory
4. **IMPORTANT: For existing deployments, run migration first:**
   - Copy and paste contents of `demos/change_failure_rate/sql/migrate-add-product.sql`
   - Click **Run**
   - Verify: `SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'incidents' AND COLUMN_NAME = 'product'`

**Option A (continued): For NEW Deployments**

1-3. (Same as above)
4. Copy and paste contents of `demos/change_failure_rate/sql/schema.sql`
5. Click **Run**
6. Verify table creation: `SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'incidents'`

**Option B: Azure Data Studio**

```bash
# Connect to SQL Server
Server: sql-dora-metrics-dfoggi.database.windows.net
Database: sqldb-deployment-frequency
Authentication: Azure Active Directory

# Run schema.sql
# Then verify:
SELECT * FROM incidents;
```

**Option C: SQL Command Line**

```bash
cd demos/change_failure_rate/sql
sqlcmd -S sql-dora-metrics-dfoggi.database.windows.net -d sqldb-deployment-frequency -G -i schema.sql
```

### 3. Grant SQL Permissions

If not already done for deployment frequency, grant the Function App's managed identity access:

```bash
# Connect to SQL Database (Azure Portal Query Editor)
# Copy and run: demos/change_failure_rate/sql/grant-permissions.sql
```

Verify permissions:
```sql
SELECT 
    dp.name AS UserName,
    r.name AS RoleName
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'dora-metrics-deploy-frequency';
```

Expected result:
- `dora-metrics-deploy-frequency` | `db_datawriter`
- `dora-metrics-deploy-frequency` | `db_datareader`

### 4. Configure Function App Environment Variables

**Add new environment variable:**

```bash
# Via Azure Portal
az functionapp config appsettings set \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --settings INCIDENT_LOOKBACK_HOURS="24"
```

**Or via Azure Portal:**
1. Navigate to: Function App → Configuration → Application settings
2. Click **+ New application setting**
3. Name: `INCIDENT_LOOKBACK_HOURS`
4. Value: `24`
5. Click **OK** → **Save**

### 5. Deploy Updated Function App

```bash
# Navigate to function app directory
cd demos/frequency-deployment

# Deploy to Azure
func azure functionapp publish dora-metrics-deploy-frequency

# Expected output:
# Getting site publishing info...
# Uploading package...
# Upload completed successfully.
# Deployment completed successfully.
# Syncing triggers...
# Functions in dora-metrics-deploy-frequency:
#     cfr_collector - [timerTrigger]
#     deployment_frequency_collector - [timerTrigger]
#     health_check - [httpTrigger]
#     lead_time_collector - [timerTrigger]
```

### 6. Verify Deployment

**Check Function Status:**

```bash
# List all functions
az functionapp function show \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --function-name cfr_collector

# Check app status
az functionapp show \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --query state
```

**Monitor Logs:**

```bash
# Stream logs in real-time
func azure functionapp logstream dora-metrics-deploy-frequency

# Look for:
# [CFR-COLLECTOR] Starting Change Failure Rate data collection...
# [CFR-COLLECTOR] Collected X incidents
# [CFR-COLLECTOR] Function completed successfully
```

**Or via Azure Portal:**
1. Function App → Functions → `cfr_collector`
2. Click **Monitor**
3. View recent executions and logs

### 7. Test Data Collection

**Create test incident with GitHub issue template:**

1. Go to any repository in your organization
2. Click **Issues** → **New Issue**
3. Select **Production Incident** template
4. Fill in the form:
   - **Product Affected**: Select `MyApp` or `ServiceApp`
   - **Incident Date & Time**: Current time
   - **Environment**: Production
   - **Incident Description**: "Test incident for CFR tracking"
   - **Impact**: "Testing product field extraction"
5. Submit issue (labels `incident` and `production` are auto-applied)
6. Wait 5 minutes for the function to run
7. Check SQL database for the incident with product field:

```sql
-- Check if incidents are being collected
SELECT COUNT(*) FROM incidents;

-- View recent incidents WITH PRODUCT
SELECT TOP 5 
    issue_number,
    repository,
    product,
    title,
    created_at,
    collected_at 
FROM incidents 
ORDER BY collected_at DESC;

-- Verify product extraction is working
SELECT 
    product,
    COUNT(*) as incident_count
FROM incidents
WHERE product IS NOT NULL
GROUP BY product
ORDER BY incident_count DESC;

-- Check correlation preview with product
SELECT 
    d.repository,
    i.product,
    d.created_at as deployment_time,
    COUNT(i.id) as incident_count
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY d.repository, i.product, d.created_at
HAVING COUNT(i.id) > 0
ORDER BY incident_count DESC;
```

## PowerBI Setup

### 1. Add Incidents Table to Data Model

1. Open PowerBI Desktop
2. **Home** → **Get Data** → **Azure SQL Database**
3. Server: `sql-dora-metrics-dfoggi.database.windows.net`
4. Database: `sqldb-deployment-frequency`
5. Select table: `incidents`
6. Click **Load**

### 2. Create DAX Measures

Create a new measure group called "Change Failure Rate":

```dax
// Total Deployments (reuse if already exists)
Total Deployments = COUNTROWS(deployments)

// Deployments with Incidents (24h time window)
Deployments With Incidents = 
CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
        ALL(deployments),
        CALCULATE(
            COUNTROWS(
                FILTER(
                    incidents,
                    incidents[repository] = deployments[repository]
                    && incidents[created_at] >= deployments[created_at]
                    && incidents[created_at] <= deployments[created_at] + 1/24
                )
            )
        ) > 0
    )
)

// CFR Percentage
CFR % = 
DIVIDE(
    [Deployments With Incidents],
    [Total Deployments],
    0
) * 100

// Total Incidents
Total Incidents = COUNTROWS(incidents)

// CFR Category (DORA Benchmark)
CFR Category = 
VAR CFRValue = [CFR %]
RETURN
    SWITCH(
        TRUE(),
        CFRValue <= 5, "Elite (0-5%)",
        CFRValue <= 10, "High (5-10%)",
        CFRValue <= 15, "Medium (10-15%)",
        CFRValue > 15, "Low (>15%)",
        "No Data"
    )

// Product-Specific Measures for MyApp
CFR % MyApp = 
VAR DeploymentsWithIncidentsMyApp = 
CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
        ALL(deployments),
        CALCULATE(
            COUNTROWS(
                FILTER(
                    incidents,
                    incidents[repository] = deployments[repository]
                    && incidents[product] = "MyApp"
                    && incidents[created_at] >= deployments[created_at]
                    && incidents[created_at] <= deployments[created_at] + 1/24
                )
            )
        ) > 0
    )
)
RETURN
DIVIDE(DeploymentsWithIncidentsMyApp, [Total Deployments], 0) * 100

// Product-Specific Measures for ServiceApp
CFR % ServiceApp = 
VAR DeploymentsWithIncidentsServiceApp = 
CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
        ALL(deployments),
        CALCULATE(
            COUNTROWS(
                FILTER(
                    incidents,
                    incidents[repository] = deployments[repository]
                    && incidents[product] = "ServiceApp"
                    && incidents[created_at] >= deployments[created_at]
                    && incidents[created_at] <= deployments[created_at] + 1/24
                )
            )
        ) > 0
    )
)
RETURN
DIVIDE(DeploymentsWithIncidentsServiceApp, [Total Deployments], 0) * 100

// Incidents by Product Count
Incidents MyApp = CALCULATE(COUNTROWS(incidents), incidents[product] = "MyApp")
Incidents ServiceApp = CALCULATE(COUNTROWS(incidents), incidents[product] = "ServiceApp")
```

### 3. Alternative: Create SQL View for Easier PowerBI

Run this in Azure SQL:

```sql
CREATE VIEW vw_cfr_analysis AS
SELECT 
    d.id as deployment_id,
    d.deployment_id as deployment_github_id,
    d.repository,
    d.environment,
    d.created_at as deployment_time,
    d.status,
    d.creator as deployer,
    i.id as incident_id,
    i.issue_number,
    i.title as incident_title,
    i.product as incident_product,
    i.created_at as incident_time,
    i.state as incident_state,
    i.labels as incident_labels,
    i.creator as incident_creator,
    DATEDIFF(MINUTE, d.created_at, i.created_at) as minutes_after_deployment,
    CAST(DATEDIFF(MINUTE, d.created_at, i.created_at) / 60.0 AS DECIMAL(10,2)) as hours_after_deployment
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.environment = 'production' 
    AND d.status = 'SUCCESS';
```

Then in PowerBI, import `vw_cfr_analysis` and use simpler measures:

```dax
// CFR % (using view)
CFR % = 
DIVIDE(
    DISTINCTCOUNT(vw_cfr_analysis[deployment_id], vw_cfr_analysis[incident_id] <> BLANK()),
    DISTINCTCOUNT(vw_cfr_analysis[deployment_id]),
    0
) * 100

// CFR % by Product (using view)
CFR % by Product = 
DIVIDE(
    DISTINCTCOUNT(
        FILTER(
            vw_cfr_analysis,
            vw_cfr_analysis[incident_id] <> BLANK()
        )[deployment_id]
    ),
    DISTINCTCOUNT(vw_cfr_analysis[deployment_id]),
    0
) * 100
```

### 4. Create Visualizations

**Page: Change Failure Rate**

**Visual 1: CFR KPI Cards (Product Breakdown)**
- Create 3 KPI cards side-by-side:
  1. Overall: `[CFR %]` with goal: 5% (Elite threshold)
  2. MyApp: `[CFR % MyApp]` with goal: 5%
  3. ServiceApp: `[CFR % ServiceApp]` with goal: 5%
- Format: Percentage with 1 decimal
- Trend axis: Date

**Visual 2: CFR Trend Line Chart**
- X-axis: `deployments[created_at]` (by week or day)
- Y-axis: `[CFR %]`
- Legend: `incidents[product]` (to show separate lines for MyApp and ServiceApp)
- Add reference lines at 5%, 10%, 15% for DORA benchmarks
- Tooltip: Show product, CFR %, and incident count

**Visual 3: CFR by Repository (Bar Chart)**
- Axis: `deployments[repository]`
- Values: `[CFR %]`
- Data labels: On
- Conditional formatting: Red >15%, Yellow 10-15%, Green <10%

**Visual 4: CFR by Product (Bar Chart)**
- Axis: `incidents[product]`
- Values: `[CFR %]`
- Data labels: On
- Shows comparison between MyApp and ServiceApp

**Visual 5: Deployment & Incident Summary (Cards)**
- Create 5 separate cards:
  - `[Total Deployments]`
  - `[Deployments With Incidents]`
  - `[Total Incidents]`
  - `[Incidents MyApp]`
  - `[Incidents ServiceApp]`

**Visual 6: Incident Details Table**
- Show: `vw_cfr_analysis` or create custom table
- Columns:
  - Deployment Time
  - Repository
  - **Product** (incidents[product])
  - Incident # (as link to GitHub)
  - Incident Title
  - Hours After Deployment
  - Incident State
- Filter: Only show rows with incidents (incident_id <> blank)
- Enable sorting and filtering on Product column

**Visual 7: CFR Category Donut Chart**
- Legend: `[CFR Category]`
- Values: Count of repositories
- Colors: Elite=Green, High=Blue, Medium=Yellow, Low=Red

### 5. Add Slicers

- **Date Range** (from deployments[created_at])
- **Repository** (multi-select)
- **Environment** (Production/Staging/Pre-Production)
- **Product** (incidents[product]) — **NEW: Enables filtering by MyApp or ServiceApp**
- **CFR Category** (Elite/High/Medium/Low)

### 6. Create Drill-Through Page

**Name:** Incident Details

**Drill-through fields:**
- Repository
- Deployment Date

**Visuals:**
1. **Table:** All incidents for selected deployment
2. **Timeline:** Show incident creation times relative to deployment
3. **KPI:** CFR for this specific repository/time period

## Validation Checklist

- [ ] GitHub App has Issues permission (Read-only)
- [ ] SQL `incidents` table exists
- [ ] Function App has `INCIDENT_LOOKBACK_HOURS` environment variable
- [ ] Function deployed successfully (check for `cfr_collector` function)
- [ ] Function logs show `[CFR-COLLECTOR]` entries
- [ ] Incidents table has data: `SELECT COUNT(*) FROM incidents`
- [ ] PowerBI has `incidents` table loaded
- [ ] PowerBI measures calculate CFR correctly
- [ ] CFR dashboard shows data

## Troubleshooting

### No Incidents Collected

**Issue:** `SELECT COUNT(*) FROM incidents` returns 0

**Solutions:**
1. Verify GitHub App permission: Settings → Apps → Check Issues = Read-only
2. Check if issues with both labels exist:
   ```bash
   # Search GitHub for: label:"incident" label:"production"
   ```
3. Check function logs for errors:
   ```bash
   func azure functionapp logstream dora-metrics-deploy-frequency | grep CFR
   ```
4. Verify environment variable:
   ```bash
   az functionapp config appsettings list \
     --name dora-metrics-deploy-frequency \
     --resource-group dora-metrics-demo-rg \
     --query "[?name=='INCIDENT_LOOKBACK_HOURS']"
   ```

### Function Not Running

**Issue:** No `[CFR-COLLECTOR]` logs

**Solutions:**
1. Check function exists:
   ```bash
   az functionapp function list \
     --name dora-metrics-deploy-frequency \
     --resource-group dora-metrics-demo-rg
   ```
2. Manually trigger function (for testing):
   ```bash
   # Via Azure Portal: Function → Code + Test → Test/Run
   ```
3. Check timer trigger is enabled:
   - Azure Portal → Function App → Functions → cfr_collector → Overview
   - Status should be "Enabled"

### PowerBI Shows No Data

**Issue:** CFR measures return blank

**Solutions:**
1. Refresh dataset: Home → Refresh
2. Check table relationships are correct
3. Verify DAX measure syntax
4. Check date filters aren't excluding all data
5. Run correlation query in SQL to verify data exists

### CFR Always 0%

**Issue:** `[Deployments With Incidents]` returns 0

**Solutions:**
1. Check time window logic in DAX
2. Verify repository names match exactly between tables
3. Test correlation in SQL:
   ```sql
   SELECT COUNT(*) FROM deployments d
   INNER JOIN incidents i 
       ON d.repository = i.repository
       AND i.created_at >= d.created_at
       AND i.created_at <= DATEADD(HOUR, 24, d.created_at);
   ```

## Monitoring & Maintenance

### Daily Checks

```bash
# Check function health
az functionapp show --name dora-metrics-deploy-frequency --resource-group dora-metrics-demo-rg --query state

# Check recent executions
az monitor activity-log list --resource-group dora-metrics-demo-rg --namespace Microsoft.Web --max-events 5
```

### Weekly Queries

```sql
-- Incidents collected this week
SELECT COUNT(*) FROM incidents 
WHERE collected_at >= DATEADD(day, -7, GETUTCDATE());

-- CFR by repository (this week)
SELECT 
    repository,
    COUNT(DISTINCT d.id) as deployments,
    COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN d.id END) as deployments_with_incidents,
    CAST(COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN d.id END) * 100.0 / COUNT(DISTINCT d.id) AS DECIMAL(5,2)) as cfr_pct
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY repository
ORDER BY cfr_pct DESC;
```

## Next Steps

1. **Standardize Labels:** Ensure all teams use `incident` + `production` labels consistently
2. **Train Teams:** Educate developers on when to create incident issues
3. **Set Alerts:** Create Azure Monitor alerts for high CFR (>15%)
4. **Root Cause Analysis:** Link incidents back to specific PRs/commits
5. **Continuous Improvement:** Review CFR trends weekly and identify patterns

## Support

- **Documentation:** [demos/change_failure_rate/README.md](README.md)
- **SQL Queries:** [demos/change_failure_rate/sql/verify-collection.sql](sql/verify-collection.sql)
- **Function Code:** [demos/frequency-deployment/function_app.py](../frequency-deployment/function_app.py)
