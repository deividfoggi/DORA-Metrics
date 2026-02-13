# DORA Deployment Frequency Collector

Azure Function App that collects deployment frequency metrics from GitHub and stores them in Azure SQL Database.

## Architecture

- **Azure Function (Timer Trigger)**: Runs daily at 1 AM UTC
- **GitHub GraphQL API**: Queries organization repositories and deployments  
- **Azure SQL Database**: Stores deployment events with Entra ID authentication
- **Managed Identity**: Securely accesses SQL without connection strings

## Prerequisites

- Azure subscription
- GitHub Personal Access Token with `repo` and `read:org` scopes
- Azure CLI installed
- Azure Functions Core Tools (for local development)

## Setup

### 1. Create Azure Resources

Resources already created:
- Resource Group: `dora-metrics-demo-rg`
- SQL Server: `sql-dora-metrics-dfoggi.database.windows.net`
- SQL Database: `sqldb-deployment-frequency`
- Function App: `dora-metrics-deploy-frequency`

### 2. Initialize Database Schema

Connect to SQL Database using Azure Data Studio or Azure Portal Query Editor and run:

```bash
sqlcmd -S tcp:sql-dora-metrics-dfoggi.database.windows.net,1433 -d sqldb-deployment-frequency -G -N -l 30 -i sql/schema.sql
```

Or execute `sql/schema.sql` contents in Azure Portal.

### 3. Grant Function App Permissions

Run these SQL commands:

```sql
CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];
ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];
```

### 4. Configure Function App Settings

```bash
az functionapp config appsettings set \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --settings \
    "SQL_SERVER=sql-dora-metrics-dfoggi.database.windows.net" \
    "SQL_DATABASE=sqldb-deployment-frequency" \
    "GITHUB_ORG_NAME=<your-org>" \
    "GITHUB_PAT=<your-token>"
```

### 5. Deploy Function Code

```bash
cd demos/frequency-deployment
func azure functionapp publish dora-metrics-deploy-frequency
```

## Local Development

### Setup

1. Create `local.settings.json`:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "SQL_SERVER": "sql-dora-metrics-dfoggi.database.windows.net",
    "SQL_DATABASE": "sqldb-deployment-frequency",
    "GITHUB_ORG_NAME": "your-org",
    "GITHUB_PAT": "your-pat"
  }
}
```

2. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. Run locally:

```bash
func start
```

## Deployment

### Option 1: Azure Functions Core Tools

```bash
func azure functionapp publish dora-metrics-deploy-frequency
```

### Option 2: GitHub Actions (CI/CD)

See `.github/workflows/deploy-function.yml` for automated deployment.

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_ORG_NAME` | GitHub organization name | Yes |
| `GITHUB_PAT` | GitHub Personal Access Token | Yes |
| `SQL_SERVER` | SQL Server FQDN | Yes |
| `SQL_DATABASE` | SQL Database name | Yes |

### Timer Schedule

The function runs daily at 1 AM UTC. To change the schedule, modify the `schedule` parameter in `function_app.py`:

```python
@app.schedule(schedule="0 0 1 * * *", ...)  # Cron format: sec min hour day month dayofweek
```

## Monitoring

### View Logs

```bash
func azure functionapp logstream dora-metrics-deploy-frequency
```

### Check Function Status

```bash
az functionapp show --name dora-metrics-deploy-frequency --resource-group dora-metrics-demo-rg --query state
```

### Query Deployment Data

```sql
-- Total deployments today
SELECT COUNT(*) FROM deployments 
WHERE CAST(created_at AS DATE) = CAST(GETUTCDATE() AS DATE);

-- Deployments by repository (last 7 days)
SELECT repository, COUNT(*) as deployment_count
FROM deployments
WHERE created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY repository
ORDER BY deployment_count DESC;

-- Deployment frequency trend
SELECT CAST(created_at AS DATE) as date, COUNT(*) as deployments
FROM deployments
WHERE created_at >= DATEADD(day, -30, GETUTCDATE())
GROUP BY CAST(created_at AS DATE)
ORDER BY date;
```

## Troubleshooting

### Function not triggering

- Check timer schedule configuration
- Verify Function App is running: `az functionapp show ...`
- Check Application Insights logs

### GitHub API errors

- Verify GITHUB_PAT is valid and has correct scopes
- Check rate limits: Token should allow 5,000 requests/hour
- Verify GITHUB_ORG_NAME is correct

### SQL connection errors

- Verify managed identity is enabled on Function App
- Confirm SQL user was created for managed identity
- Check SQL firewall allows Azure services

### Authentication issues

- Ensure Function App has system-assigned managed identity enabled
- Verify SQL permissions were granted correctly
- Check Azure AD authentication is working

## Cost Estimate

- **Function App (Consumption)**: ~$0.20/month (1 execution/day)
- **SQL Database (Serverless)**: ~$5-10/month
- **Application Insights**: ~$0-2/month (5GB free tier)

**Total**: ~$5-12/month

## Next Steps

1. Add dashboard/visualization (Power BI)
2. Implement pre-aggregation for faster queries
3. Add alerting for deployment anomalies
4. Expand to other DORA metrics (Lead Time, CFR, MTTR)
5. Add team/product metadata enrichment
