-- ============================================
-- Verify Lead Time for Changes Implementation
-- Run this in Azure Portal Query Editor
-- ============================================

-- Check if PRs are being collected
SELECT 
    COUNT(*) as total_prs,
    COUNT(DISTINCT repository) as unique_repos,
    MIN(collected_at) as first_collection,
    MAX(collected_at) as last_collection
FROM pull_requests;
GO

-- View recent PRs
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

-- Check PR-Deployment correlation
SELECT 
    COUNT(DISTINCT pr.id) as total_prs,
    COUNT(DISTINCT d.id) as prs_with_deployments,
    COUNT(DISTINCT pr.id) - COUNT(DISTINCT d.id) as undeployed_prs,
    CAST(COUNT(DISTINCT d.id) * 100.0 / NULLIF(COUNT(DISTINCT pr.id), 0) AS DECIMAL(5,2)) as correlation_rate
FROM pull_requests pr
LEFT JOIN deployments d ON pr.merge_commit_sha = d.commit_sha;
GO

-- View correlated PR-Deployment pairs with lead time
SELECT TOP 10
    pr.repository,
    pr.pr_number,
    pr.title,
    pr.created_at as pr_created,
    pr.merged_at as pr_merged,
    d.created_at as deployed_at,
    d.environment,
    d.status,
    DATEDIFF(MINUTE, pr.created_at, d.created_at) as lead_time_minutes,
    DATEDIFF(HOUR, pr.created_at, d.created_at) as lead_time_hours
FROM pull_requests pr
INNER JOIN deployments d ON pr.merge_commit_sha = d.commit_sha
ORDER BY d.created_at DESC;
GO

-- Summary stats
SELECT 
    'Pull Requests' as metric,
    COUNT(*) as count
FROM pull_requests
UNION ALL
SELECT 
    'Deployments' as metric,
    COUNT(*) as count
FROM deployments
UNION ALL
SELECT 
    'Correlated PR-Deployments' as metric,
    COUNT(DISTINCT pr.id) as count
FROM pull_requests pr
INNER JOIN deployments d ON pr.merge_commit_sha = d.commit_sha;
GO
