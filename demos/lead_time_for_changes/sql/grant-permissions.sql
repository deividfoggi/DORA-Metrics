-- Grant permissions to Azure Function App managed identity
-- Run this after creating the schema
-- Replace [dora-metrics-deploy-frequency] with your Function App name

-- Create user from managed identity
CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;

-- Grant read/write permissions
ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];
ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];

-- Verify permissions
SELECT 
    dp.name AS principal_name,
    dp.type_desc AS principal_type,
    r.name AS role_name
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'dora-metrics-deploy-frequency';
