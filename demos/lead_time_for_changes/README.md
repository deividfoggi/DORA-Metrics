# DORA Lead Time for Changes

Implementation for tracking Lead Time for Changes DORA metric by collecting Pull Request data from GitHub and correlating with deployments.

## Overview

This implementation extends the existing deployment frequency collector to track **Lead Time for Changes** - the time from PR creation to production deployment. It follows DORA methodology where lead time is measured from when code is committed (PR created) to when it's running in production.

## Architecture

- **Azure Function (Timer Trigger)**: Runs every 5 minutes (same schedule as deployments)
- **GitHub GraphQL API**: Queries merged pull requests to `main` branch
- **Azure SQL Database**: Stores PR data and links to deployments via commit SHA
- **PowerBI**: Joins PRs and deployments to calculate median lead time

## How It Works

1. **PR Collection**: Function collects merged PRs from the last 48 hours
2. **Data Storage**: PRs stored with merge commit SHA, created/merged timestamps
3. **Correlation**: PowerBI joins `pull_requests.merge_commit_sha = deployments.commit_sha`
4. **Lead Time Calculation**: `DATEDIFF(deployments.created_at - pr.created_at)`

## Database Schema

The `pull_requests` table stores merged PR data:

```sql
CREATE TABLE pull_requests (
    id INT IDENTITY(1,1) PRIMARY KEY,
    pr_number INT NOT NULL,
    repository NVARCHAR(255) NOT NULL,
    title NVARCHAR(500),
    author NVARCHAR(255),
    created_at DATETIME2 NOT NULL,       -- PR creation time
    merged_at DATETIME2 NOT NULL,        -- When PR merged to main
    merge_commit_sha NVARCHAR(40) NOT NULL,  -- Links to deployments
    base_branch NVARCHAR(255) NOT NULL,
    collected_at DATETIME2 NOT NULL,
    CONSTRAINT UQ_pr_repo_number UNIQUE (repository, pr_number)
);
```

## Setup

### 1. Create Database Table

Connect to the same SQL database used for deployment frequency and run:

```bash
sqlcmd -S tcp:sql-dora-metrics-dfoggi.database.windows.net,1433 -d sqldb-deployment-frequency -G -N -l 30 -i demos/lead_time_for_changes/sql/schema.sql
```

The schema creates the `pull_requests` table in the existing database.

### 2. Update GitHub App Permissions

Your existing GitHub App needs **Pull Requests: Read** permission:

1. Go to GitHub → Settings → Developer Settings → GitHub Apps → Your App
2. Permissions → Repository Permissions → Pull Requests → **Read-only**
3. Save changes
4. Install & Authorize the updated permissions for your organization

### 3. Configure Function App

Add these environment variables to your existing Function App (`dora-metrics-deploy-frequency`):

```bash
# Optional - defaults provided
BASE_BRANCH="main"               # Branch to track (default: main)
PR_LOOKBACK_HOURS="48"          # Hours to look back for PRs (default: 48)
```

All other configuration (GITHUB_ORG_NAME, GITHUB_APP_ID, etc.) is already set from deployment frequency setup.

### 4. Deploy Updated Function

The PR collection function is added to `demos/frequency-deployment/function_app.py`:

```bash
cd demos/frequency-deployment
func azure functionapp publish dora-metrics-deploy-frequency
```

## Verification

### Check PR Collection

Query the database to verify PRs are being collected:

```sql
-- Check recent PR collection
SELECT TOP 10 
    repository, 
    pr_number, 
    title,
    created_at,
    merged_at,
    merge_commit_sha,
    collected_at
FROM pull_requests
ORDER BY collected_at DESC;

-- Check PR-deployment correlation
SELECT 
    COUNT(DISTINCT pr.id) as total_prs,
    COUNT(DISTINCT d.id) as matched_deployments,
    COUNT(DISTINCT pr.merge_commit_sha) as unique_commits
FROM pull_requests pr
LEFT JOIN deployments d ON pr.merge_commit_sha = d.commit_sha
WHERE pr.collected_at >= DATEADD(day, -1, GETUTCDATE());
```

### Monitor Function Logs

Check Application Insights or Function App logs for:

```
[PR-COLLECTOR] Collecting pull request data from GitHub...
[PR-COLLECTOR] Collected X pull requests
[PR-COLLECTOR] Successfully stored X pull requests
[PR-COLLECTOR] CORRELATION: X PRs, Y matching deployments
```

## PowerBI Integration

### Data Model

Create relationship in PowerBI:
- `pull_requests[merge_commit_sha]` → `deployments[commit_sha]` (Many-to-One)

### Lead Time Calculation

Create calculated column in PowerBI:

```dax
Lead Time (Minutes) = 
    DATEDIFF(
        RELATED(pull_requests[created_at]),
        deployments[created_at],
        MINUTE
    )
```

### Median Lead Time Metric

```dax
Median Lead Time (Hours) = 
    DIVIDE(
        PERCENTILE.INC(deployments[Lead Time (Minutes)], 0.5),
        60,
        0
    )
```

### DORA Performance Classification

```dax
Performance Level = 
    VAR MedianHours = [Median Lead Time (Hours)]
    RETURN
        SWITCH(
            TRUE(),
            MedianHours < 24, "Elite (<1 day)",
            MedianHours < 168, "High (1-7 days)",
            MedianHours < 720, "Medium (1 week-1 month)",
            "Low (>1 month)"
        )
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_BRANCH` | `main` | Branch to track for PR merges (typically main/master) |
| `PR_LOOKBACK_HOURS` | `48` | How many hours back to collect merged PRs |
| `GITHUB_ORG_NAME` | Required | GitHub organization name (already configured) |
| `GITHUB_APP_ID` | Required | GitHub App ID (already configured) |
| `GITHUB_APP_INSTALLATION_ID` | Required | Installation ID (already configured) |
| `GITHUB_APP_PRIVATE_KEY` | Required | Private key (already configured) |
| `SQL_SERVER` | Required | SQL server (already configured) |
| `SQL_DATABASE` | Required | Database name (already configured) |

## SAGAS3 Pilot Testing

For the SAGAS3 pilot, this will track PRs merged to `main` in:
- `sagas3-etl`
- `sagas3-api`
- `sagas3-ui`
- `sagas3-ui-bff-realtime`

Since "merge to main = production deployment", lead time = PR creation → merge → deployment event.

## Troubleshooting

### No PRs Collected

1. Check GitHub App has "Pull Requests: Read" permission
2. Verify PRs are merged to the branch specified in `BASE_BRANCH`
3. Check logs for GraphQL errors
4. Ensure PRs exist in the lookback window (default 48 hours)

### PRs Not Linking to Deployments

1. Verify `merge_commit_sha` matches `commit_sha` in deployments table
2. Check that deployments are being created for the merge commits
3. Run correlation query above to see match rate
4. Consider increasing `PR_LOOKBACK_HOURS` if deployments lag behind merges

### Permission Errors

Ensure the managed identity has access to the `pull_requests` table:

```sql
-- Verify permissions
SELECT dp.name, r.name AS role_name
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'dora-metrics-deploy-frequency';
```

## DORA Benchmarks (2023)

| Performance Level | Median Lead Time |
|-------------------|------------------|
| **Elite** | Less than 1 day |
| **High** | 1 day to 1 week |
| **Medium** | 1 week to 1 month |
| **Low** | More than 1 month |

Source: 2023 Accelerate State of DevOps Report, Google

## Next Steps

1. ✅ Deploy schema to SQL database
2. ✅ Update GitHub App permissions
3. ✅ Deploy updated Function App
4. ⏳ Monitor PR collection for 24 hours
5. ⏳ Verify PR-deployment correlation
6. ⏳ Build PowerBI dashboard with lead time visualizations
7. ⏳ Test with SAGAS3 repositories
8. ⏳ Roll out to additional teams
