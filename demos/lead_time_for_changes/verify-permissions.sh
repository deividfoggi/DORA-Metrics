#!/bin/bash
# Verify and grant permissions for Lead Time for Changes
# Run this after deploy-schema.sh

set -e  # Exit on error

# Configuration (update these if different)
SQL_SERVER="sql-dora-metrics-dfoggi.database.windows.net"
SQL_DATABASE="sqldb-deployment-frequency"
FUNCTION_APP_NAME="dora-metrics-deploy-frequency"

echo "================================================"
echo "Verifying Database Permissions"
echo "================================================"
echo "Server: $SQL_SERVER"
echo "Database: $SQL_DATABASE"
echo "Function App: $FUNCTION_APP_NAME"
echo ""

echo "Checking if managed identity has database access..."
sqlcmd -S "$SQL_SERVER" -d "$SQL_DATABASE" -G -N -l 30 << EOF
-- Check if user exists and has correct permissions
SELECT 
    dp.name AS principal_name,
    dp.type_desc AS principal_type,
    r.name AS role_name
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = '$FUNCTION_APP_NAME';
GO

-- Verify pull_requests table exists
SELECT 
    SCHEMA_NAME(schema_id) + '.' + name AS table_name,
    type_desc
FROM sys.objects 
WHERE name IN ('pull_requests', 'deployments')
ORDER BY name;
GO
EOF

echo ""
echo "✅ Permissions verified!"
echo ""
echo "If the managed identity user doesn't exist or lacks permissions, run:"
echo "  sqlcmd -S $SQL_SERVER -d $SQL_DATABASE -G -N -Q \"CREATE USER [$FUNCTION_APP_NAME] FROM EXTERNAL PROVIDER; ALTER ROLE db_datawriter ADD MEMBER [$FUNCTION_APP_NAME]; ALTER ROLE db_datareader ADD MEMBER [$FUNCTION_APP_NAME];\""
