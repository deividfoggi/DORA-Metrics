-- ============================================================================
-- DORA Metrics - Unified Database Schema
-- Creates all tables for the four DORA metrics:
--   1. Deployment Frequency (deployments, deployment_metrics_daily, repositories)
--   2. Lead Time for Changes (pull_requests)
--   3. Change Failure Rate (incidents)
--   4. Time to Restore Service (uses incidents.created_at and incidents.closed_at)
--
-- Run this script in Azure Portal Query Editor or Azure Data Studio
-- Connect to: sql-dora-metrics-dfoggi.database.windows.net
-- Database: sqldb-deployment-frequency
-- Authentication: Azure Active Directory
-- ============================================================================

-- ============================================================================
-- 1. DEPLOYMENT FREQUENCY TABLES
-- ============================================================================

-- Main deployments table - stores deployment events from GitHub
CREATE TABLE deployments (
    id INT IDENTITY(1,1) PRIMARY KEY,
    deployment_id NVARCHAR(255) NOT NULL UNIQUE,
    repository NVARCHAR(255) NOT NULL,
    environment NVARCHAR(50) NOT NULL,
    commit_sha NVARCHAR(40) NOT NULL,
    created_at DATETIME2 NOT NULL,
    creator NVARCHAR(255),
    status NVARCHAR(50),
    status_updated_at DATETIME2,
    collected_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    INDEX IX_deployments_repository (repository),
    INDEX IX_deployments_created_at (created_at),
    INDEX IX_deployments_environment (environment)
);
GO

-- Daily aggregated deployment metrics table
CREATE TABLE deployment_metrics_daily (
    id INT IDENTITY(1,1) PRIMARY KEY,
    date DATE NOT NULL,
    repository NVARCHAR(255) NOT NULL,
    environment NVARCHAR(50) NOT NULL,
    total_deployments INT NOT NULL,
    successful_deployments INT NOT NULL,
    failed_deployments INT NOT NULL,
    calculated_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_metrics_daily UNIQUE (date, repository, environment),
    INDEX IX_metrics_date (date),
    INDEX IX_metrics_repository (repository)
);
GO

-- Repository metadata table (for team/product enrichment)
CREATE TABLE repositories (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL UNIQUE,
    team NVARCHAR(255),
    product NVARCHAR(255),
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    updated_at DATETIME2 NOT NULL DEFAULT GETUTCDATE()
);
GO

-- ============================================================================
-- 2. LEAD TIME FOR CHANGES TABLE
-- ============================================================================

-- Pull requests table - stores merged PRs for lead time calculation
-- Linked to deployments via merge_commit_sha = deployments.commit_sha
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
GO

-- ============================================================================
-- 3. CHANGE FAILURE RATE / TIME TO RESTORE TABLE
-- ============================================================================

-- Incidents table - stores GitHub Issues with labels "incident" AND "production"
-- Also used for Time to Restore Service: DATEDIFF(created_at, closed_at)
CREATE TABLE incidents (
    id INT IDENTITY(1,1) PRIMARY KEY,
    issue_number INT NOT NULL,
    repository NVARCHAR(255) NOT NULL,
    title NVARCHAR(500),
    created_at DATETIME2 NOT NULL,
    closed_at DATETIME2,
    state NVARCHAR(50) NOT NULL,  -- 'open' or 'closed'
    labels NVARCHAR(MAX),  -- JSON array of all labels
    product NVARCHAR(255),  -- Product affected (extracted from issue body)
    creator NVARCHAR(255),
    url NVARCHAR(500),
    collected_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_incident_repo_number UNIQUE (repository, issue_number),
    INDEX IX_incidents_repository (repository),
    INDEX IX_incidents_created_at (created_at),
    INDEX IX_incidents_state (state),
    INDEX IX_incidents_product (product),
    INDEX IX_incidents_collected_at (collected_at)
);
GO

-- ============================================================================
-- 4. POWERBI VIEWS (Optional - for easier data consumption)
-- ============================================================================

-- View: Change Failure Rate analysis (deployments correlated with incidents)
CREATE VIEW vw_cfr_analysis AS
SELECT 
    d.id as deployment_id,
    d.deployment_id as deployment_github_id,
    d.repository,
    d.environment,
    d.created_at as deployment_time,
    d.status,
    d.creator as deployer,
    i.id as incident_id,
    i.issue_number,
    i.title as incident_title,
    i.product as incident_product,
    i.created_at as incident_time,
    i.state as incident_state,
    i.labels as incident_labels,
    i.creator as incident_creator,
    DATEDIFF(MINUTE, d.created_at, i.created_at) as minutes_after_deployment,
    CAST(DATEDIFF(MINUTE, d.created_at, i.created_at) / 60.0 AS DECIMAL(10,2)) as hours_after_deployment
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.environment = 'production' 
    AND d.status = 'SUCCESS';
GO

-- View: Lead Time for Changes (PRs linked to deployments)
CREATE VIEW vw_lead_time_analysis AS
SELECT 
    pr.id as pr_id,
    pr.pr_number,
    pr.repository,
    pr.title as pr_title,
    pr.author,
    pr.created_at as pr_created_at,
    pr.merged_at as pr_merged_at,
    pr.first_commit_date,
    pr.merge_commit_sha,
    pr.base_branch,
    d.id as deployment_id,
    d.environment,
    d.created_at as deployed_at,
    d.status as deployment_status,
    -- Lead time from first commit to deployment (canonical DORA)
    DATEDIFF(MINUTE, COALESCE(pr.first_commit_date, pr.created_at), d.created_at) as lead_time_minutes,
    CAST(DATEDIFF(MINUTE, COALESCE(pr.first_commit_date, pr.created_at), d.created_at) / 60.0 AS DECIMAL(10,2)) as lead_time_hours,
    -- Lead time from PR creation to deployment (alternative)
    DATEDIFF(MINUTE, pr.created_at, d.created_at) as lead_time_from_pr_minutes
FROM pull_requests pr
LEFT JOIN deployments d ON pr.merge_commit_sha = d.commit_sha;
GO

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'Schema deployment completed!' AS Status;

SELECT 
    name AS table_name,
    type_desc
FROM sys.objects 
WHERE type IN ('U', 'V')  -- U = User Table, V = View
    AND name IN ('deployments', 'deployment_metrics_daily', 'repositories', 
                 'pull_requests', 'incidents', 'vw_cfr_analysis', 'vw_lead_time_analysis')
ORDER BY type_desc, name;
GO

-- After creating the schema, run grant-permissions.sql to grant access to the Function App
