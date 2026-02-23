-- ============================================================================
-- DORA Metrics - Grant Function App Managed Identity Access
-- Run these commands in Azure Portal Query Editor or Azure Data Studio
-- Connect to: sql-dora-metrics-dfoggi.database.windows.net
-- Database: sqldb-deployment-frequency
-- Authentication: Azure Active Directory
-- ============================================================================

-- Step 1: Create user for the Function App's managed identity
-- (Skip if already created - the command will error harmlessly)
CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;
GO

-- Step 2: Grant data writer permissions (INSERT, UPDATE, DELETE)
-- Required for: deployments, deployment_metrics_daily, repositories,
--               pull_requests, incidents tables
ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];
GO

-- Step 3: Grant data reader permissions (SELECT)
-- Required for: MERGE operations, verification queries, correlation stats
ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];
GO

-- Step 4: Verify permissions
SELECT 
    dp.name AS UserName,
    dp.type_desc AS UserType,
    r.name AS RoleName
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'dora-metrics-deploy-frequency';
GO

-- Step 5: Verify all DORA tables exist
SELECT 
    name AS table_name,
    type_desc
FROM sys.objects 
WHERE type IN ('U', 'V')
    AND name IN ('deployments', 'deployment_metrics_daily', 'repositories', 
                 'pull_requests', 'incidents', 'vw_cfr_analysis', 'vw_lead_time_analysis')
ORDER BY type_desc, name;
GO

-- Expected output:
-- UserName: dora-metrics-deploy-frequency | UserType: EXTERNAL_USER | RoleName: db_datawriter
-- UserName: dora-metrics-deploy-frequency | UserType: EXTERNAL_USER | RoleName: db_datareader
