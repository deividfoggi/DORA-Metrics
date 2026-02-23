-- ============================================================================
-- DORA Metrics - Unified Verification Script
-- Run this in Azure Portal Query Editor to verify all metrics collection
-- ============================================================================

-- ============================================================================
-- 1. DEPLOYMENT FREQUENCY - Verify deployments are being collected
-- ============================================================================
PRINT '=== DEPLOYMENT FREQUENCY ==='

SELECT 
    COUNT(*) as total_deployments,
    COUNT(DISTINCT repository) as unique_repos,
    MIN(collected_at) as first_collection,
    MAX(collected_at) as last_collection
FROM deployments;
GO

-- Recent deployments
SELECT TOP 10
    repository,
    environment,
    status,
    created_at,
    creator,
    collected_at
FROM deployments
ORDER BY collected_at DESC;
GO

-- Deployments by repository (last 7 days)
SELECT 
    repository,
    environment,
    COUNT(*) as deployment_count,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN status IN ('FAILURE', 'ERROR') THEN 1 ELSE 0 END) as failed
FROM deployments
WHERE created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY repository, environment
ORDER BY deployment_count DESC;
GO

-- ============================================================================
-- 2. LEAD TIME FOR CHANGES - Verify PRs are being collected
-- ============================================================================
PRINT '=== LEAD TIME FOR CHANGES ==='

SELECT 
    COUNT(*) as total_prs,
    COUNT(DISTINCT repository) as unique_repos,
    MIN(collected_at) as first_collection,
    MAX(collected_at) as last_collection
FROM pull_requests;
GO

-- Recent PRs
SELECT TOP 10
    repository,
    pr_number,
    title,
    author,
    created_at,
    merged_at,
    base_branch,
    collected_at
FROM pull_requests
ORDER BY collected_at DESC;
GO

-- PR-Deployment correlation (lead time data)
SELECT 
    COUNT(DISTINCT pr.id) as total_prs,
    COUNT(DISTINCT d.id) as prs_with_deployments,
    COUNT(DISTINCT pr.id) - COUNT(DISTINCT d.id) as undeployed_prs,
    CAST(COUNT(DISTINCT d.id) * 100.0 / NULLIF(COUNT(DISTINCT pr.id), 0) AS DECIMAL(5,2)) as correlation_rate
FROM pull_requests pr
LEFT JOIN deployments d ON pr.merge_commit_sha = d.commit_sha;
GO

-- Lead time samples (correlated PR-Deployment pairs)
SELECT TOP 10
    pr.repository,
    pr.pr_number,
    pr.title,
    pr.created_at as pr_created,
    pr.merged_at as pr_merged,
    d.created_at as deployed_at,
    d.environment,
    d.status,
    DATEDIFF(MINUTE, COALESCE(pr.first_commit_date, pr.created_at), d.created_at) as lead_time_minutes,
    CAST(DATEDIFF(MINUTE, COALESCE(pr.first_commit_date, pr.created_at), d.created_at) / 60.0 AS DECIMAL(10,2)) as lead_time_hours
FROM pull_requests pr
INNER JOIN deployments d ON pr.merge_commit_sha = d.commit_sha
ORDER BY d.created_at DESC;
GO

-- ============================================================================
-- 3. CHANGE FAILURE RATE - Verify incidents are being collected
-- ============================================================================
PRINT '=== CHANGE FAILURE RATE ==='

SELECT 
    COUNT(*) as total_incidents,
    COUNT(DISTINCT repository) as unique_repos,
    MIN(collected_at) as first_collection,
    MAX(collected_at) as last_collection
FROM incidents;
GO

-- Recent incidents
SELECT TOP 10
    repository,
    issue_number,
    title,
    product,
    state,
    created_at,
    closed_at,
    collected_at
FROM incidents
ORDER BY collected_at DESC;
GO

-- Incidents by state
SELECT 
    state,
    COUNT(*) as count
FROM incidents
GROUP BY state;
GO

-- Time-based correlation: incidents within 24h of deployments
SELECT TOP 10
    d.repository,
    d.deployment_id,
    d.environment,
    d.created_at as deployment_time,
    i.issue_number,
    i.title as incident_title,
    i.product,
    i.created_at as incident_time,
    DATEDIFF(MINUTE, d.created_at, i.created_at) as minutes_after_deployment
FROM deployments d
INNER JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.created_at >= DATEADD(day, -7, GETUTCDATE())
ORDER BY d.created_at DESC, i.created_at ASC;
GO

-- CFR calculation (last 30 days)
WITH deployments_with_incidents AS (
    SELECT 
        CAST(d.created_at AS DATE) as date,
        d.repository,
        d.environment,
        d.id as deployment_id,
        CASE 
            WHEN EXISTS (
                SELECT 1 FROM incidents i 
                WHERE i.repository = d.repository
                AND i.created_at >= d.created_at
                AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
            ) THEN 1 ELSE 0 
        END as has_incident
    FROM deployments d
    WHERE d.created_at >= DATEADD(day, -30, GETUTCDATE())
        AND d.status = 'SUCCESS'
        AND d.environment = 'production'
)
SELECT 
    date,
    repository,
    COUNT(deployment_id) as total_deployments,
    SUM(has_incident) as deployments_with_incidents,
    CAST(SUM(has_incident) * 100.0 / COUNT(deployment_id) AS DECIMAL(5,2)) as cfr_percentage
FROM deployments_with_incidents
GROUP BY date, repository
ORDER BY date DESC, repository;
GO

-- ============================================================================
-- 4. TIME TO RESTORE SERVICE - Derived from incidents
-- ============================================================================
PRINT '=== TIME TO RESTORE SERVICE ==='

-- Average time to restore (closed incidents only)
SELECT 
    repository,
    COUNT(*) as closed_incidents,
    AVG(DATEDIFF(MINUTE, created_at, closed_at)) as avg_restore_minutes,
    CAST(AVG(DATEDIFF(MINUTE, created_at, closed_at)) / 60.0 AS DECIMAL(10,2)) as avg_restore_hours,
    MIN(DATEDIFF(MINUTE, created_at, closed_at)) as min_restore_minutes,
    MAX(DATEDIFF(MINUTE, created_at, closed_at)) as max_restore_minutes
FROM incidents
WHERE state = 'closed' AND closed_at IS NOT NULL
GROUP BY repository
ORDER BY avg_restore_minutes DESC;
GO

-- ============================================================================
-- 5. OVERALL SUMMARY
-- ============================================================================
PRINT '=== OVERALL SUMMARY ==='

SELECT 'Deployments' as metric, COUNT(*) as count FROM deployments
UNION ALL
SELECT 'Pull Requests' as metric, COUNT(*) as count FROM pull_requests
UNION ALL
SELECT 'Incidents' as metric, COUNT(*) as count FROM incidents
UNION ALL
SELECT 'Correlated PR-Deployments' as metric, COUNT(DISTINCT pr.id) as count
FROM pull_requests pr
INNER JOIN deployments d ON pr.merge_commit_sha = d.commit_sha
UNION ALL
SELECT 'Deployments with Incidents (24h)' as metric, COUNT(DISTINCT d.id) as count
FROM deployments d
INNER JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at);
GO

PRINT 'Verification complete!'
