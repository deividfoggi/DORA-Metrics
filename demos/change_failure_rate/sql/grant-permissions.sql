-- Grant Function App Managed Identity Access to SQL Database
-- Run these commands in Azure Portal Query Editor or Azure Data Studio
-- Connect to: sql-dora-metrics-dfoggi.database.windows.net
-- Database: sqldb-deployment-frequency
-- Authentication: Azure Active Directory

-- Step 1: Create user for the Function App's managed identity
-- (Skip if already created for deployment frequency)
CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;

-- Step 2: Grant data writer permissions (INSERT, UPDATE, DELETE)
ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];

-- Step 3: Grant data reader permissions (SELECT)
ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];

-- Step 4: Verify permissions
SELECT 
    dp.name AS UserName,
    dp.type_desc AS UserType,
    r.name AS RoleName
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'dora-metrics-deploy-frequency';
