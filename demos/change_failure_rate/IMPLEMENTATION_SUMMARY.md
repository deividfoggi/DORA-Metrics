# Change Failure Rate Enhancement - Implementation Summary

## Overview
Enhanced the Change Failure Rate demo to support product filtering (MyApp and ServiceApp) in Power BI by:
- Standardizing incident creation with GitHub issue templates
- Extracting product information from issue body
- Storing product field in database
- Enabling product-based filtering and analysis in Power BI

## Products Configured
- **MyApp**
- **ServiceApp**

## Changes Made

### 1. GitHub Templates Updated
**Files Modified:**
- [demos/change_failure_rate/github_templates/incident.yml](demos/change_failure_rate/github_templates/incident.yml)
  - Updated product dropdown from "Product A/B/C" to "MyApp/ServiceApp"
  
- [demos/change_failure_rate/github_templates/sync-incident-to-project.yml](demos/change_failure_rate/github_templates/sync-incident-to-project.yml)
  - Updated product mapping for GitHub Projects integration

### 2. Database Schema Enhanced
**Files Modified:**
- [demos/change_failure_rate/sql/schema.sql](demos/change_failure_rate/sql/schema.sql)
  - Added `product NVARCHAR(255)` column to incidents table
  - Added index `IX_incidents_product` for query performance

**Files Created:**
- [demos/change_failure_rate/sql/migrate-add-product.sql](demos/change_failure_rate/sql/migrate-add-product.sql)
  - **IMPORTANT**: Migration script for existing deployments
  - Idempotent (safe to run multiple times)
  - Must be run BEFORE deploying updated function

### 3. Azure Function Enhanced
**Files Modified:**
- [demos/frequency-deployment/function_app.py](demos/frequency-deployment/function_app.py)
  - Added `bodyText` field to GraphQL query
  - Implemented regex pattern to extract product: `/### Product Affected\s*\n\s*(.+)/`
  - Updated `store_incidents()` to include product in MERGE statement
  - Product extraction happens during collection (no validation/rejection)

### 4. Documentation Updated
**Files Modified:**
- [demos/change_failure_rate/README.md](demos/change_failure_rate/README.md)
  - Added GitHub issue template usage instructions
  - Documented product extraction mechanism
  - Added product-filtered DAX measures for Power BI
  - Updated visualizations to include product filtering

- [demos/change_failure_rate/DEPLOYMENT.md](demos/change_failure_rate/DEPLOYMENT.md)
  - Added migration script instructions for existing deployments
  - Added product-specific DAX measures (CFR % MyApp, CFR % ServiceApp)
  - Updated SQL view to include product column
  - Enhanced visualizations with product breakdown
  - Added product slicer setup instructions

**Files Created:**
- [demos/change_failure_rate/sql/verify-product-collection.sql](demos/change_failure_rate/sql/verify-product-collection.sql)
  - Comprehensive validation queries
  - Product coverage analysis
  - CFR by product calculations
  - Health checks for product data collection

## Deployment Steps (For Existing Installations)

### Step 1: Run Database Migration
**CRITICAL**: Run this FIRST before deploying updated function

```bash
# Via Azure Portal Query Editor:
# 1. Navigate to SQL Database
# 2. Open Query Editor
# 3. Run: demos/change_failure_rate/sql/migrate-add-product.sql
```

### Step 2: Deploy GitHub Issue Templates
```bash
# For each repository that should report incidents:
# 1. Copy demos/change_failure_rate/github_templates/incident.yml 
#    to .github/ISSUE_TEMPLATE/ in the repository
# 2. Commit and push
```

### Step 3: Deploy Updated Function
```bash
cd demos/frequency-deployment
func azure functionapp publish dora-metrics-deploy-frequency
```

### Step 4: Verify Collection
Wait 5-10 minutes, then run:
```bash
# Connect to Azure SQL and run:
# demos/change_failure_rate/sql/verify-product-collection.sql
```

### Step 5: Update Power BI
1. Refresh dataset to load new product column
2. Add new DAX measures (see DEPLOYMENT.md section 2)
3. Add product slicer to reports
4. Update visualizations to show product breakdown

## Key Features

### Product Extraction
- **Automatic**: Parses product from GitHub issue form during collection
- **Free-form**: Accepts any value from template dropdown (no validation)
- **Forward-only**: Only new incidents will have product field populated
- **Pattern**: Uses regex to extract from issue body markdown

### Power BI Capabilities
- **Product Slicer**: Filter entire report by MyApp or ServiceApp
- **Product-Specific CFR**: Separate measures for each product
- **Product Trends**: Line charts showing CFR over time by product
- **Product Comparison**: Bar charts comparing CFR across products

### Database Design
- **Nullable Column**: `product NVARCHAR(255)` allows NULL for backward compatibility
- **Indexed**: Fast filtering and grouping by product
- **Idempotent**: MERGE statement prevents duplicates

## Validation Queries

### Check Product Coverage
```sql
SELECT 
    COUNT(*) as total_incidents,
    COUNT(product) as incidents_with_product,
    CAST(COUNT(product) * 100.0 / COUNT(*) AS DECIMAL(5,2)) as coverage_pct
FROM incidents;
```

### Product Distribution
```sql
SELECT 
    product,
    COUNT(*) as incident_count
FROM incidents
WHERE product IS NOT NULL
GROUP BY product
ORDER BY incident_count DESC;
```

### CFR by Product (Last 7 Days)
```sql
SELECT 
    i.product,
    COUNT(DISTINCT d.id) as deployments,
    COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN d.id END) as deployments_with_incidents,
    CAST(COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN d.id END) * 100.0 / COUNT(DISTINCT d.id) AS DECIMAL(5,2)) as cfr_pct
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.created_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY i.product
ORDER BY cfr_pct DESC;
```

## Expected Outcomes

### Immediate (After Deployment)
- ✅ New incidents will have product field populated
- ✅ Migration adds product column to existing table
- ✅ Function logs show product extraction in debug messages

### Short Term (1-2 weeks)
- ✅ Product coverage increases as new incidents are created
- ✅ Power BI shows product distribution across incidents
- ✅ CFR metrics can be filtered by product

### Long Term (1+ month)
- ✅ Sufficient data for product-based trend analysis
- ✅ Product-specific CFR targets and benchmarks
- ✅ Root cause analysis by product

## Troubleshooting

### Product Field is NULL for New Incidents
**Possible Causes:**
1. Issue template not deployed to repository
2. User created issue manually (not using template)
3. Template structure doesn't match regex pattern

**Solutions:**
1. Verify template exists in `.github/ISSUE_TEMPLATE/incident.yml`
2. Educate users to use issue template (not create blank issue)
3. Check function logs for regex match failures

### Product Values Unexpected
**Possible Causes:**
1. Users typing instead of selecting from dropdown
2. Template modified with different options

**Solutions:**
1. Issue template uses dropdown (should prevent typing)
2. Verify template options match: MyApp, ServiceApp
3. Allow free-form values (no validation in function)

### Migration Script Fails
**Possible Causes:**
1. Column already exists (not a problem - script is idempotent)
2. Permission issues

**Solutions:**
1. Check error message - if "column already exists", ignore (safe)
2. Verify managed identity has db_datawriter role
3. Run as database admin if needed

## Files Summary

### Created (5 files)
1. `demos/change_failure_rate/sql/migrate-add-product.sql` - Database migration
2. `demos/change_failure_rate/sql/verify-product-collection.sql` - Validation queries

### Modified (5 files)
1. `demos/change_failure_rate/github_templates/incident.yml` - Product dropdown
2. `demos/change_failure_rate/github_templates/sync-incident-to-project.yml` - Product mapping
3. `demos/change_failure_rate/sql/schema.sql` - Added product column
4. `demos/frequency-deployment/function_app.py` - Product extraction logic
5. `demos/change_failure_rate/README.md` - Product documentation
6. `demos/change_failure_rate/DEPLOYMENT.md` - Power BI setup with products

## Next Steps

1. **Test in Non-Production**: Deploy to test environment first
2. **Verify Migration**: Run migration script and verify column exists
3. **Deploy Function**: Update Azure Function with new code
4. **Create Test Incident**: Use issue template to create test incident
5. **Verify Collection**: Run verify-product-collection.sql
6. **Update Power BI**: Add product measures and slicers
7. **Train Users**: Educate teams on using issue template

## Support & References

- **Main Documentation**: [demos/change_failure_rate/README.md](demos/change_failure_rate/README.md)
- **Deployment Guide**: [demos/change_failure_rate/DEPLOYMENT.md](demos/change_failure_rate/DEPLOYMENT.md)
- **Verification Script**: [demos/change_failure_rate/sql/verify-product-collection.sql](demos/change_failure_rate/sql/verify-product-collection.sql)
- **Migration Script**: [demos/change_failure_rate/sql/migrate-add-product.sql](demos/change_failure_rate/sql/migrate-add-product.sql)

---

**Implementation Date**: February 5, 2026
**Products**: MyApp, ServiceApp
**Collection Strategy**: Forward-only (no backfill)
**Validation Strategy**: Free-form (no rejection of unexpected values)
