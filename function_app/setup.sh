#!/bin/bash
# Setup script for DORA Deployment Frequency Metrics
# This script initializes the SQL database schema and grants permissions

set -e

# Variables (set these if not already in environment)
SQL_SERVER="${SQL_SERVER:-sql-dora-metrics-dfoggi}"
SQL_DB="${SQL_DB:-sqldb-deployment-frequency}"
FUNCTION_APP="${FUNCTION_APP:-dora-metrics-deploy-frequency}"
RESOURCE_GROUP="${RESOURCE_GROUP:-dora-metrics-demo-rg}"

echo "======================================"
echo "DORA Metrics Setup Script"
echo "======================================"
echo "SQL Server: ${SQL_SERVER}.database.windows.net"
echo "Database: $SQL_DB"
echo "Function App: $FUNCTION_APP"
echo ""

# Step 1: Create database schema
echo "Step 1: Creating database schema..."
echo "Run this command in Azure Data Studio or Query Editor:"
echo ""
echo "sqlcmd -S tcp:${SQL_SERVER}.database.windows.net,1433 -d $SQL_DB -G -N -l 30 -i sql/schema.sql"
echo ""
echo "Or copy the contents of sql/schema.sql and execute in Azure Portal Query Editor"
echo ""
read -p "Press Enter once you've created the schema..."

# Step 2: Grant Function App managed identity access to SQL Database
echo ""
echo "Step 2: Granting Function App access to SQL Database..."
echo "Run these SQL commands in Query Editor:"
echo ""
echo "CREATE USER [$FUNCTION_APP] FROM EXTERNAL PROVIDER;"
echo "ALTER ROLE db_datawriter ADD MEMBER [$FUNCTION_APP];"
echo "ALTER ROLE db_datareader ADD MEMBER [$FUNCTION_APP];"
echo ""
read -p "Press Enter once you've granted permissions..."

# Step 3: Configure Function App settings
echo ""
echo "Step 3: Configuring Function App settings..."

az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --settings \
    "SQL_SERVER=${SQL_SERVER}.database.windows.net" \
    "SQL_DATABASE=$SQL_DB" \
    "GITHUB_ORG_NAME=<YOUR_GITHUB_ORG>" \
    "GITHUB_PAT=<YOUR_GITHUB_PAT>"

echo ""
echo "⚠️  IMPORTANT: Update GITHUB_ORG_NAME and GITHUB_PAT in Azure Portal:"
echo "   1. Go to Function App → Configuration → Application settings"
echo "   2. Update GITHUB_ORG_NAME with your GitHub organization name"
echo "   3. Update GITHUB_PAT with your GitHub Personal Access Token"
echo "   4. Required PAT scopes: repo, read:org"
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Deploy the function code: func azure functionapp publish $FUNCTION_APP"
echo "2. Test the function: Use Azure Portal to run manually"
echo "3. Monitor logs: func azure functionapp logstream $FUNCTION_APP"
