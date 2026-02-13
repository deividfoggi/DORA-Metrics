-- DORA Change Failure Rate Database Schema
-- Creates table for storing incident data from GitHub Issues

-- Incidents table - stores GitHub Issues with labels "incident" AND "production"
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

-- Grant Function App managed identity access (run separately after schema creation)
-- CREATE USER [dora-metrics-deploy-frequency] FROM EXTERNAL PROVIDER;
-- ALTER ROLE db_datawriter ADD MEMBER [dora-metrics-deploy-frequency];
-- ALTER ROLE db_datareader ADD MEMBER [dora-metrics-deploy-frequency];
