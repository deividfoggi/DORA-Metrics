-- ============================================
-- Lead Time for Changes - SQL Schema
-- Copy and paste this into Azure Portal Query Editor
-- ============================================

-- Step 1: Create pull_requests table
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

-- Step 2: Verify table was created
SELECT 'pull_requests table created!' AS Status;
SELECT name, type_desc FROM sys.objects WHERE name = 'pull_requests';
GO

-- Step 3: Verify permissions (should already exist from deployment frequency)
SELECT 
    dp.name AS principal_name,
    dp.type_desc AS principal_type,
    r.name AS role_name
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'dora-metrics-deploy-frequency';
GO

-- Expected output: You should see db_datawriter and db_datareader roles
-- If not, run the grant-permissions.sql file
