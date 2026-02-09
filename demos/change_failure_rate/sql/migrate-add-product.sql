-- Migration Script: Add product column to incidents table
-- This script adds product tracking to existing incidents table
-- Run this on existing deployments BEFORE deploying the updated function

-- Add product column
IF NOT EXISTS (
    SELECT 1 
    FROM sys.columns 
    WHERE object_id = OBJECT_ID('incidents') 
    AND name = 'product'
)
BEGIN
    ALTER TABLE incidents
    ADD product NVARCHAR(255);
    
    PRINT 'Added product column to incidents table';
END
ELSE
BEGIN
    PRINT 'Product column already exists';
END
GO

-- Add index on product for filtering performance
IF NOT EXISTS (
    SELECT 1 
    FROM sys.indexes 
    WHERE name = 'IX_incidents_product' 
    AND object_id = OBJECT_ID('incidents')
)
BEGIN
    CREATE INDEX IX_incidents_product ON incidents(product);
    
    PRINT 'Added index IX_incidents_product';
END
ELSE
BEGIN
    PRINT 'Index IX_incidents_product already exists';
END
GO

-- Verify changes
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'incidents'
ORDER BY ORDINAL_POSITION;

PRINT 'Migration completed successfully';
