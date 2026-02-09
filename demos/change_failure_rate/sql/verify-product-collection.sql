-- Verification Script: Validate Product Field Collection
-- Run this script to verify that product information is being collected from GitHub issues

-- ============================================================================
-- 1. Check if product column exists
-- ============================================================================
PRINT 'Checking product column schema...'
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'incidents' AND COLUMN_NAME = 'product';
GO

-- ============================================================================
-- 2. Count incidents with product data
-- ============================================================================
PRINT 'Checking product data availability...'
SELECT 
    COUNT(*) as total_incidents,
    COUNT(product) as incidents_with_product,
    COUNT(*) - COUNT(product) as incidents_without_product,
    CAST(COUNT(product) * 100.0 / NULLIF(COUNT(*), 0) AS DECIMAL(5,2)) as product_coverage_pct
FROM incidents;
GO

-- ============================================================================
-- 3. Product distribution
-- ============================================================================
PRINT 'Product distribution across incidents...'
SELECT 
    ISNULL(product, '(null)') as product,
    COUNT(*) as incident_count,
    MIN(created_at) as first_incident,
    MAX(created_at) as last_incident
FROM incidents
GROUP BY product
ORDER BY incident_count DESC;
GO

-- ============================================================================
-- 4. Recent incidents with product information
-- ============================================================================
PRINT 'Recent incidents (last 10)...'
SELECT TOP 10
    issue_number,
    repository,
    product,
    title,
    created_at,
    state,
    collected_at
FROM incidents
ORDER BY collected_at DESC;
GO

-- ============================================================================
-- 5. Product extraction validation (check for expected values)
-- ============================================================================
PRINT 'Validating product values (should be MyApp or ServiceApp)...'
SELECT 
    product,
    COUNT(*) as count,
    CASE 
        WHEN product IN ('MyApp', 'ServiceApp') THEN 'Valid'
        WHEN product IS NULL THEN 'Missing'
        ELSE 'Unexpected Value'
    END as validation_status
FROM incidents
GROUP BY product
ORDER BY count DESC;
GO

-- ============================================================================
-- 6. Incidents by repository and product (last 30 days)
-- ============================================================================
PRINT 'Incidents by repository and product (last 30 days)...'
SELECT 
    repository,
    ISNULL(product, '(no product)') as product,
    COUNT(*) as incident_count,
    MIN(created_at) as first_incident,
    MAX(created_at) as last_incident
FROM incidents
WHERE created_at >= DATEADD(day, -30, GETUTCDATE())
GROUP BY repository, product
ORDER BY repository, incident_count DESC;
GO

-- ============================================================================
-- 7. CFR analysis by product (deployments with incidents by product)
-- ============================================================================
PRINT 'CFR preview by product (last 7 days)...'
SELECT 
    i.product,
    COUNT(DISTINCT d.id) as total_deployments,
    COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN d.id END) as deployments_with_incidents,
    COUNT(DISTINCT i.id) as total_incidents,
    CAST(
        COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN d.id END) * 100.0 
        / NULLIF(COUNT(DISTINCT d.id), 0) 
        AS DECIMAL(5,2)
    ) as cfr_percentage
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.created_at >= DATEADD(day, -7, GETUTCDATE())
    AND d.environment = 'production'
GROUP BY i.product
ORDER BY cfr_percentage DESC;
GO

-- ============================================================================
-- 8. Sample incidents with full details (for manual verification)
-- ============================================================================
PRINT 'Sample incident details for manual verification...'
SELECT TOP 5
    issue_number,
    repository,
    product,
    title,
    created_at,
    state,
    labels,
    url,
    collected_at
FROM incidents
WHERE product IS NOT NULL
ORDER BY collected_at DESC;
GO

-- ============================================================================
-- 9. Issues needing attention (missing product data on recent incidents)
-- ============================================================================
PRINT 'Recent incidents missing product data (may need template update)...'
SELECT TOP 10
    issue_number,
    repository,
    title,
    created_at,
    url,
    collected_at
FROM incidents
WHERE product IS NULL
    AND created_at >= DATEADD(day, -7, GETUTCDATE())
ORDER BY created_at DESC;
GO

-- ============================================================================
-- 10. Collection health check
-- ============================================================================
PRINT 'Collection health check (incidents collected in last 24 hours)...'
SELECT 
    CAST(collected_at AS DATE) as collection_date,
    COUNT(*) as incidents_collected,
    COUNT(product) as incidents_with_product,
    COUNT(DISTINCT repository) as repositories_with_incidents,
    COUNT(DISTINCT product) as unique_products
FROM incidents
WHERE collected_at >= DATEADD(day, -1, GETUTCDATE())
GROUP BY CAST(collected_at AS DATE)
ORDER BY collection_date DESC;
GO

PRINT 'Verification complete!'
PRINT 'Expected products: MyApp, ServiceApp'
PRINT 'If seeing unexpected values or high null percentage, verify:'
PRINT '1. GitHub issue template is deployed to repositories'
PRINT '2. Users are selecting product from dropdown (not manually typing)'
PRINT '3. Azure Function regex pattern matches template structure'
