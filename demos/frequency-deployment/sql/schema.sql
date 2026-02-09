-- DORA Deployment Frequency Database Schema
-- Creates tables for storing deployment data from GitHub

-- Main deployments table
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

-- Daily aggregated metrics table
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

-- Repository metadata table (optional - for future use)
CREATE TABLE repositories (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL UNIQUE,
    team NVARCHAR(255),
    product NVARCHAR(255),
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    updated_at DATETIME2 NOT NULL DEFAULT GETUTCDATE()
);

-- Grant Function App managed identity access (run separately after schema creation)
-- CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;
-- ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];
-- ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];
