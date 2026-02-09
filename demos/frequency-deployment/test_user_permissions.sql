-- Check if your user exists and what permissions they have
SELECT 
    dp.name AS UserName,
    dp.type_desc AS UserType,
    r.name AS RoleName
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'admin@MngEnvMCAP380802.onmicrosoft.com'
   OR dp.name LIKE '%dfoggi%'
ORDER BY dp.name, r.name;
