-- DORA Lead Time for Changes Database Schema
-- Creates tables for storing pull request data from GitHub
-- PRs are linked to deployments via merge_commit_sha for lead time calculation

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
    first_commit_date DATETIME2,  -- First commit authored date (canonical DORA T1)
    collected_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_pr_repo_number UNIQUE (repository, pr_number),
    INDEX IX_pr_repository (repository),
    INDEX IX_pr_merged_at (merged_at),
    INDEX IX_pr_merge_commit_sha (merge_commit_sha),
    INDEX IX_pr_base_branch (base_branch),
    INDEX IX_pr_first_commit_date (first_commit_date)
);

-- Note: The deployments table already exists in the deployment frequency database
-- For PowerBI, join pull_requests to deployments on:
--   pull_requests.merge_commit_sha = deployments.commit_sha
-- 
-- Lead time calculation in PowerBI (canonical DORA - uses first commit date):
--   lead_time_minutes = DATEDIFF(MINUTE, 
--       COALESCE(pull_requests.first_commit_date, pull_requests.created_at), 
--       deployments.created_at)
--
-- COALESCE ensures fallback to PR created_at if first_commit_date is unavailable
--
-- Example PowerBI DAX for median lead time:
--   Median Lead Time = 
--     PERCENTILE.INC(
--         FILTER(deployments, deployments[commit_sha] IN VALUES(pull_requests[merge_commit_sha])),
--         [lead_time_minutes],
--         0.5
--     )
--
-- Alternative: both perspectives available
--   lead_time_from_commit = DATEDIFF(MINUTE, pull_requests.first_commit_date, deployments.created_at)
--   lead_time_from_pr     = DATEDIFF(MINUTE, pull_requests.created_at, deployments.created_at)

-- Grant Function App managed identity access (run separately after schema creation)
-- CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;
-- ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];
-- ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];
