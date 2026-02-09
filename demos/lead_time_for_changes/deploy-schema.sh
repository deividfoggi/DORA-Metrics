#!/bin/bash
# Deploy Lead Time for Changes SQL Schema
# Run this script to create the pull_requests table

set -e  # Exit on error

# Configuration (update these if different)
SQL_SERVER="sql-dora-metrics-dfoggi.database.windows.net"
SQL_DATABASE="sqldb-deployment-frequency"

echo "================================================"
echo "Deploying Lead Time for Changes SQL Schema"
echo "================================================"
echo "Server: $SQL_SERVER"
echo "Database: $SQL_DATABASE"
echo ""

# Create the pull_requests table
echo "Creating pull_requests table..."
sqlcmd -S "$SQL_SERVER" -d "$SQL_DATABASE" -G -N -l 30 << 'EOF'
-- Pull requests table - stores merged PRs for lead time tracking
CREATE TABLE pull_requests (
    id INT IDENTITY(1,1) PRIMARY KEY,
    pr_number INT NOT NULL,
    repository NVARCHAR(255) NOT NULL,
    title NVARCHAR(500),
    author NVARCHAR(255),
    created_at DATETIME2 NOT NULL,
    merged_at DATETIME2 NOT NULL,
    merge_commit_sha NVARCHAR(40) NOT NULL,
    base_branch NVARCHAR(255) NOT NULL,
    collected_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_pr_repo_number UNIQUE (repository, pr_number),
    INDEX IX_pr_repository (repository),
    INDEX IX_pr_merged_at (merged_at),
    INDEX IX_pr_merge_commit_sha (merge_commit_sha),
    INDEX IX_pr_base_branch (base_branch)
);
GO

-- Verify table was created
SELECT 'Table created successfully!' AS Status;
SELECT name, type_desc FROM sys.objects WHERE name = 'pull_requests';
GO
EOF

echo ""
echo "✅ Schema deployment completed!"
echo ""
echo "Next step: Verify permissions with deploy-permissions.sh"
