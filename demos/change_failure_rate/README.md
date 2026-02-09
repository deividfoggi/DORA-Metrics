# DORA Change Failure Rate

## Overview

This implementation collects **Change Failure Rate (CFR)** data by tracking GitHub Issues labeled as production incidents. CFR measures the percentage of deployments that cause failures in production.

Following the DORA framework, CFR is calculated as:
```
CFR = (Deployments with Incidents / Total Deployments) × 100
```

## Architecture

- **Azure Function (Timer Trigger)**: Runs every 5 minutes (same schedule as deployments)
- **GitHub GraphQL API**: Queries Issues with labels "incident" AND "production"
- **Azure SQL Database**: Stores raw incident data in `incidents` table
- **PowerBI**: Performs time-based correlation and CFR calculation

## How It Works

### Data Collection (Azure Function)
1. **Incident Collection**: Function collects GitHub Issues with BOTH labels: `incident` AND `production`
2. **Product Extraction**: Parses the product field from GitHub issue form template (`MyApp` or `ServiceApp`)
3. **Time Window**: Collects incidents from the last 24 hours
4. **Raw Storage**: Issues stored in `incidents` table with all metadata (issue #, title, product, created_at, state, labels, etc.)

### Correlation & Analysis (PowerBI)
PowerBI performs time-based correlation:
- **Rule**: An incident is linked to a deployment if it was created within 24 hours AFTER the deployment
- **Matching Criteria**: Same repository + incident created between `deployment.created_at` and `deployment.created_at + 24h`

Example DAX/SQL logic:
```sql
-- PowerBI will join incidents to deployments like this:
SELECT d.*, i.*
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.environment = 'production'
```

## Setup

### Prerequisites
- Existing deployment frequency function app deployed
- Azure SQL Database with deployments table
- GitHub App with Issues read permission

### 1. Add GitHub App Permission

The GitHub App needs read access to Issues:

1. Go to: GitHub Organization Settings → GitHub Apps → Your App
2. Navigate to: Permissions → Repository permissions
3. Set **Issues** → **Read-only**
4. Click **Save changes**
5. Organization admins must accept the permission update

### 2. Create SQL Schema

Run the schema creation script:

```bash
cd demos/change_failure_rate

# For NEW deployments:
# Run sql/schema.sql (includes product column)

# For EXISTING deployments:
# Run sql/migrate-add-product.sql FIRST to add product column
# This migration script is idempotent and safe to run multiple times
```

Deploy via Azure Portal Query Editor:
```sql
-- For existing deployments, run FIRST:
-- sql/migrate-add-product.sql

-- Then verify schema:
-- sql/schema.sql (for reference)
```

The schema includes:
- `incidents` table with `product` column for filtering
- Indexes on `product`, `repository`, `created_at` for query performance
- Idempotent MERGE operations to prevent duplicates

### 3. Grant Permissions

If not already granted from deployment frequency setup:

```bash
# Run sql/grant-permissions.sql in Azure Portal Query Editor
```

### 4. Configure Function App

Add environment variable to your existing Function App (`dora-metrics-deploy-frequency`):

```bash
# Optional - defaults provided
INCIDENT_LOOKBACK_HOURS="24"    # Hours to look back for incidents (default: 24)
```

All other configuration is inherited from deployment frequency setup.

### 5. Deploy Updated Function

The incident collection function is added to `demos/frequency-deployment/function_app.py`:

```bash
cd demos/frequency-deployment
func azure functionapp publish dora-metrics-deploy-frequency
```

## Incident Label Requirements

For issues to be collected as incidents, they **MUST** have BOTH labels:
- ✅ `incident` (or `production-incident`)
- ✅ `production` (or `environment:production`)

Examples of valid issue labels:
- `incident` + `production` ✅
- `incident` + `environment:production` ✅
- `production-incident` + `production` ✅

Examples that will NOT be collected:
- Only `incident` ❌ (missing production label)
- Only `production` ❌ (missing incident label)
- `bug` + `production` ❌ (not labeled as incident)

### GitHub Issue Template

Use the standardized issue template in `github_templates/incident.yml` to ensure consistent incident reporting:

**Template Features:**
- **Product Dropdown** (required): Select from `MyApp` or `ServiceApp`
- **Incident Date & Time** (required): When the incident occurred
- **Environment** (required): Production, Staging, or Pre-Production
- **Incident Description** (required): What happened
- **Impact** (required): Effect on users/system
- **Severity** (optional): Critical, High, Medium, or Low
- **Resolution Action** (optional): How it was fixed

**Setup Instructions:**
1. Copy `demos/change_failure_rate/github_templates/incident.yml` to `.github/ISSUE_TEMPLATE/` in your repository
2. Copy `demos/change_failure_rate/github_templates/sync-incident-to-project.yml` to `.github/workflows/` if using GitHub Projects
3. Commit and push the templates
4. New incident issues will automatically apply the `incident` and `production` labels

**Product Field Extraction:**
The Azure Function automatically extracts the product selection from the issue body using regex pattern:
```python
product_match = re.search(r'### Product Affected\\s*\\n\\s*(.+)', issue["bodyText"])
```

This allows filtering and analysis by product in Power BI.

## Verification

### Check Incident Collection

```bash
# Connect to Azure SQL and run:
cd demos/change_failure_rate
# Run sql/verify-collection.sql
```

Key queries:
```sql
-- View recent incidents
SELECT TOP 10 * FROM incidents ORDER BY collected_at DESC;

-- See time-based correlation preview
SELECT d.repository, d.deployment_id, d.created_at,
       i.issue_number, i.created_at as incident_time,
       DATEDIFF(MINUTE, d.created_at, i.created_at) as minutes_after
FROM deployments d
INNER JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
ORDER BY d.created_at DESC;
```

## PowerBI Integration

### Data Model

**Tables:**
- `deployments` (existing)
- `incidents` (new)

**Relationship:**
PowerBI creates the correlation dynamically using DAX measures (no physical relationship needed).

### DAX Measures

```dax
// Count deployments with incidents (24h window)
Deployments With Incidents = 
CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
        deployments,
        CALCULATE(
            COUNTROWS(
                FILTER(
                    incidents,
                    incidents[repository] = deployments[repository] &&
                    incidents[created_at] >= deployments[created_at] &&
                    incidents[created_at] <= deployments[created_at] + 1
                )
            )
        ) > 0
    )
)

// Total deployments
Total Deployments = DISTINCTCOUNT(deployments[id])

// CFR Percentage
CFR % = 
DIVIDE(
    [Deployments With Incidents],
    [Total Deployments],
    0
) * 100

// Incident Count
Total Incidents = COUNTROWS(incidents)

// Product-Filtered CFR (for MyApp)
CFR % MyApp = 
VAR DeploymentsWithIncidentsMyApp = 
CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
        deployments,
        CALCULATE(
            COUNTROWS(
                FILTER(
                    incidents,
                    incidents[repository] = deployments[repository] &&
                    incidents[product] = "MyApp" &&
                    incidents[created_at] >= deployments[created_at] &&
                    incidents[created_at] <= deployments[created_at] + 1
                )
            )
        ) > 0
    )
)
RETURN
DIVIDE(DeploymentsWithIncidentsMyApp, [Total Deployments], 0) * 100

// Product-Filtered CFR (for ServiceApp)
CFR % ServiceApp = 
VAR DeploymentsWithIncidentsServiceApp = 
CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
        deployments,
        CALCULATE(
            COUNTROWS(
                FILTER(
                    incidents,
                    incidents[repository] = deployments[repository] &&
                    incidents[product] = "ServiceApp" &&
                    incidents[created_at] >= deployments[created_at] &&
                    incidents[created_at] <= deployments[created_at] + 1
                )
            )
        ) > 0
    )
)
RETURN
DIVIDE(DeploymentsWithIncidentsServiceApp, [Total Deployments], 0) * 100

// Incidents by Product
Incidents by Product = 
CALCULATE(
    COUNTROWS(incidents),
    ALLEXCEPT(incidents, incidents[product])
)
```

### Alternative: SQL View Approach

Create a view for easier PowerBI consumption:

```sql
CREATE VIEW vw_cfr_analysis AS
SELECT 
    d.id as deployment_id,
    d.repository,
    d.environment,
    d.created_at as deployment_time,
    d.status,
    i.id as incident_id,
    i.issue_number,
    i.title as incident_title,
    i.product as incident_product,
    i.created_at as incident_time,
    DATEDIFF(MINUTE, d.created_at, i.created_at) as minutes_after_deployment
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.environment = 'production' AND d.status = 'SUCCESS';

-- Then in PowerBI:
-- CFR % = DIVIDE(DISTINCTCOUNT(vw_cfr_analysis[deployment_id] where incident_id IS NOT NULL), 
--                DISTINCTCOUNT(vw_cfr_analysis[deployment_id])) * 100
-- Add product slicer using incident_product column
```

### Visualizations

1. **CFR Trend (Line Chart)**
   - X-axis: Date (from deployments)
   - Y-axis: CFR %
   - Legend: Product (to show separate lines for MyApp and ServiceApp)
   - Shows CFR percentage over time by product

2. **CFR by Repository (Bar Chart)**
   - X-axis: Repository
   - Y-axis: CFR %
   - Compare CFR across repositories

3. **CFR by Product (Bar Chart)**
   - X-axis: Product (MyApp, ServiceApp)
   - Y-axis: CFR %
   - Compare CFR across products

4. **Deployments vs Incidents (KPI Cards)**
   - Total Deployments
   - Deployments With Incidents
   - CFR %
   - Total Incidents
   - CFR % MyApp
   - CFR % ServiceApp

5. **Incident Details Table**
   - Columns: Deployment Time, Repository, Product, Incident #, Incident Title, Time After Deployment
   - Filterable by date range, repository, and product

6. **Product Slicer**
   - Add slicer for `incidents[product]` field
   - Allows filtering entire report by MyApp or ServiceApp

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INCIDENT_LOOKBACK_HOURS` | Hours to look back for incidents | 24 |

### Timer Schedule

Runs every 5 minutes (same as deployment collector):
```python
@app.schedule(schedule="0 */5 * * * *", ...)
```

## Monitoring

### View Logs

```bash
func azure functionapp logstream dora-metrics-deploy-frequency
```

Look for log entries with `[CFR-COLLECTOR]` prefix.

### Check Function Status

```bash
az functionapp show --name dora-metrics-deploy-frequency --resource-group dora-metrics-demo-rg --query state
```

### Query Incident Data

```sql
-- Total incidents today
SELECT COUNT(*) FROM incidents 
WHERE CAST(collected_at AS DATE) = CAST(GETUTCDATE() AS DATE);

-- Incidents by repository (last 7 days)
SELECT repository, COUNT(*) as incident_count
FROM incidents
WHERE created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY repository
ORDER BY incident_count DESC;

-- Recent deployments with incidents
SELECT 
    d.repository,
    d.created_at as deployment_time,
    COUNT(i.id) as incident_count
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY d.id, d.repository, d.created_at
HAVING COUNT(i.id) > 0
ORDER BY d.created_at DESC;
```

## DORA Benchmarks

Based on 2023 DORA research:

| Performance Level | CFR Threshold |
|------------------|---------------|
| Elite | 0-5% |
| High | 5-10% |
| Medium | 10-15% |
| Low | >15% |

## Troubleshooting

### No Incidents Being Collected

1. **Check GitHub App Permissions**: Ensure Issues permission is set to Read-only and accepted
2. **Verify Labels**: Issues must have BOTH `incident` AND `production` labels
3. **Check Logs**: Look for errors in function logs
4. **Test GitHub Query**: Manually query GitHub Issues API to verify issues exist

### Incidents Not Correlating to Deployments

1. **Check Repository Names**: Must match exactly between deployments and incidents
2. **Verify Time Window**: Incidents must be created within 24h AFTER deployment
3. **Check PowerBI DAX**: Ensure correlation logic is correctly implemented

### Missing Data in PowerBI

1. **Refresh Dataset**: Ensure PowerBI is refreshing from Azure SQL
2. **Check Filters**: Verify no filters are excluding data
3. **Run verify-collection.sql**: Check if correlation query returns results

## Best Practices

1. **Standardize Labels**: Ensure all teams use consistent labels (`incident` + `production`)
2. **Quick Incident Creation**: Create incident issues immediately when problems are detected
3. **Link to Deployments**: Reference deployment IDs or commit SHAs in issue descriptions
4. **Review CFR Trends**: Monitor CFR weekly to identify quality degradation early
5. **Post-Incident Reviews**: For each incident, document root cause and prevention steps

## Next Steps

1. **Standardize Incident Labels**: Define label taxonomy across all repositories
2. **Train Teams**: Educate developers on when and how to create incident issues
3. **Set CFR Targets**: Establish team-specific CFR goals based on DORA benchmarks
4. **Automated Alerting**: Create alerts when CFR exceeds thresholds
5. **Root Cause Analysis**: Link incidents to specific code changes for deeper analysis

## Related Metrics

- **Deployment Frequency**: How often deployments occur
- **Lead Time for Changes**: Time from PR creation to deployment
- **Time to Restore Service**: Track using incident `created_at` and `closed_at` timestamps
