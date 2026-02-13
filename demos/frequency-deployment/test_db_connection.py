#!/usr/bin/env python3
"""
Test script to debug SQL Database connection locally
"""
import os
import pyodbc
from azure.identity import DefaultAzureCredential

# Configuration
SQL_SERVER = "sql-dora-metrics-dfoggi.database.windows.net"
SQL_DATABASE = "sqldb-deployment-frequency"

print("=" * 60)
print("Testing SQL Database Connection")
print("=" * 60)

try:
    # Step 1: Get token
    print("\n[1] Getting access token...")
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    print(f"✓ Token acquired (length: {len(token.token)} chars)")
    
    # Step 2: Build connection string
    print("\n[2] Building connection string...")
    connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SQL_SERVER},1433;Database={SQL_DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
    print(f"✓ Connection string: {connection_string}")
    
    # Step 3: Encode token
    print("\n[3] Encoding token...")
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    token_bytes = token.token.encode('utf-16-le')
    print(f"✓ Token encoded ({len(token_bytes)} bytes)")
    
    # Step 4: Attempt connection
    print("\n[4] Attempting connection...")
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_bytes})
    print("✓ Connection successful!")
    
    # Step 5: Test query
    print("\n[5] Testing query...")
    cursor = conn.cursor()
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"✓ Found {len(tables)} tables: {', '.join(tables)}")
    
    # Step 6: Test insert permissions
    print("\n[6] Testing insert permissions...")
    cursor.execute("SELECT COUNT(*) FROM deployments")
    count = cursor.fetchone()[0]
    print(f"✓ Current deployments count: {count}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    
except pyodbc.Error as e:
    print(f"\n✗ pyodbc.Error: {e}")
    print(f"  Error code: {e.args[0] if e.args else 'N/A'}")
    if len(e.args) > 1:
        print(f"  Error message: {e.args[1]}")
except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
    import traceback
    print(f"\nFull traceback:")
    print(traceback.format_exc())
