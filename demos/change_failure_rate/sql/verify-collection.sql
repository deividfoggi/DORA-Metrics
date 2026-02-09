-- ============================================
-- Verify Change Failure Rate Implementation
-- Run this in Azure Portal Query Editor
-- ============================================

-- Check if incidents are being collected
SELECT 
    COUNT(*) as total_incidents,
    COUNT(DISTINCT repository) as unique_repos,
    MIN(collected_at) as first_collection,
    MAX(collected_at) as last_collection
FROM incidents;
GO

-- View recent incidents
SELECT TOP 10
    repository,
    issue_number,
    title,
    state,
    created_at,
    closed_at,
    labels,
    creator,
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

-- Incidents by repository (last 30 days)
SELECT 
    repository,
    COUNT(*) as incident_count,
    SUM(CASE WHEN state = 'open' THEN 1 ELSE 0 END) as open_incidents,
    SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as closed_incidents
FROM incidents
WHERE created_at >= DATEADD(day, -30, GETUTCDATE())
GROUP BY repository
ORDER BY incident_count DESC;
GO

-- Time-based correlation preview for PowerBI
-- Shows incidents that occurred within 24h after deployments
SELECT 
    d.repository,
    d.deployment_id,
    d.environment,
    d.created_at as deployment_time,
    i.issue_number,
    i.title as incident_title,
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

-- Change Failure Rate calculation (last 30 days)
-- This is what PowerBI will calculate
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

-- Summary stats
SELECT 
    'Incidents' as metric,
    COUNT(*) as count
FROM incidents
UNION ALL
SELECT 
    'Deployments' as metric,
    COUNT(*) as count
FROM deployments
UNION ALL
SELECT 
    'Deployments with Incidents (24h window)' as metric,
    COUNT(DISTINCT d.id) as count
FROM deployments d
WHERE EXISTS (
    SELECT 1 FROM incidents i 
    WHERE i.repository = d.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
);
GO
