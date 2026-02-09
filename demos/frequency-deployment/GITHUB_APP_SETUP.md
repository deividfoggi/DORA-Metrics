# GitHub App Setup Guide

This guide explains how to create and configure a GitHub App for DORA metrics collection.

## Why GitHub App Instead of PAT?

**Benefits:**
- ✅ Higher rate limits (5,000 req/hour per installation)
- ✅ Organization-level installation with granular permissions
- ✅ Better security (app-level authentication, not tied to user)
- ✅ Audit trail (actions appear as the app, not a user)
- ✅ Automatic credential rotation (tokens expire after 1 hour)

## Step 1: Create GitHub App

1. Go to your organization settings: `https://github.com/organizations/thefoggi/settings/apps`
2. Click **"New GitHub App"**
3. Fill in the details:

### Basic Information
- **GitHub App name**: `DORA Metrics Collector`
- **Homepage URL**: `https://github.com/thefoggi`
- **Webhook**: Uncheck "Active" (we don't need webhooks for timer-based collection)

### Permissions

Under **Repository permissions**:
- **Deployments**: Read-only
- **Metadata**: Read-only
- **Contents**: Read-only (optional, if you want commit details)

Under **Organization permissions**:
- **Members**: Read-only (optional, for user mapping)

### Where can this GitHub App be installed?
- Select **"Only on this account"** (thefoggi organization)

4. Click **"Create GitHub App"**

## Step 2: Generate Private Key

1. After creating the app, scroll to **"Private keys"** section
2. Click **"Generate a private key"**
3. A `.pem` file will download - **save this securely!**
4. The content looks like:
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA...
   ...
   -----END RSA PRIVATE KEY-----
   ```

## Step 3: Install the App to Your Organization

1. Go to **"Install App"** in the left sidebar
2. Click **"Install"** next to your organization (thefoggi)
3. Choose:
   - **All repositories** (recommended for org-wide metrics)
   - Or select specific repositories
4. Click **"Install"**

## Step 4: Get App Credentials

After installation, you need three values:

### 1. App ID
- Go to app settings: `https://github.com/organizations/thefoggi/settings/apps/[app-name]`
- Find **"App ID"** near the top (e.g., `123456`)

### 2. Installation ID
- Go to: `https://github.com/organizations/thefoggi/settings/installations`
- Click **"Configure"** next to your app
- Look at the URL: `https://github.com/organizations/thefoggi/settings/installations/[INSTALLATION_ID]`
- The number in the URL is your Installation ID (e.g., `12345678`)

### 3. Private Key
- Open the downloaded `.pem` file
- Copy the entire contents (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`)

## Step 5: Configure Azure Function App

### Option 1: Store as Plaintext (Simple, less secure)

```bash
# Set the private key as an environment variable (escape newlines)
PRIVATE_KEY=$(cat /path/to/your-app.pem)

az functionapp config appsettings set \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --settings \
    "GITHUB_APP_ID=123456" \
    "GITHUB_APP_INSTALLATION_ID=12345678" \
    "GITHUB_APP_PRIVATE_KEY=$PRIVATE_KEY"
```

### Option 2: Store as Base64 (Recommended)

```bash
# Convert private key to base64 to avoid newline issues
PRIVATE_KEY_B64=$(cat /path/to/your-app.pem | base64)

az functionapp config appsettings set \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --settings \
    "GITHUB_APP_ID=123456" \
    "GITHUB_APP_INSTALLATION_ID=12345678" \
    "GITHUB_APP_PRIVATE_KEY=$PRIVATE_KEY_B64"
```

### Option 3: Use Azure Key Vault (Most Secure)

```bash
# Create Key Vault if not exists
az keyvault create \
  --name kv-dora-metrics \
  --resource-group dora-metrics-demo-rg \
  --location brazilsouth

# Store private key
cat /path/to/your-app.pem | az keyvault secret set \
  --vault-name kv-dora-metrics \
  --name github-app-private-key \
  --file /dev/stdin

# Grant Function App access
FUNCTION_PRINCIPAL_ID=$(az functionapp identity show \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --query principalId -o tsv)

az keyvault set-policy \
  --name kv-dora-metrics \
  --object-id $FUNCTION_PRINCIPAL_ID \
  --secret-permissions get list

# Configure Function App to use Key Vault reference
az functionapp config appsettings set \
  --name dora-metrics-deploy-frequency \
  --resource-group dora-metrics-demo-rg \
  --settings \
    "GITHUB_APP_ID=123456" \
    "GITHUB_APP_INSTALLATION_ID=12345678" \
    "GITHUB_APP_PRIVATE_KEY=@Microsoft.KeyVault(SecretUri=https://kv-dora-metrics.vault.azure.net/secrets/github-app-private-key/)"
```

## Step 6: Verify Configuration

### Test Authentication Locally

```python
import jwt
import time
import requests

# Your credentials
APP_ID = "123456"
INSTALLATION_ID = "12345678"
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----"""

# Generate JWT
now = int(time.time())
payload = {
    "iat": now - 60,
    "exp": now + (10 * 60),
    "iss": APP_ID
}
jwt_token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

# Get installation token
headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept": "application/vnd.github+json"
}
response = requests.post(
    f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens",
    headers=headers
)

print(f"Status: {response.status_code}")
print(f"Token: {response.json().get('token', 'Error')[:20]}...")
```

### Test in Azure Function

1. Deploy the updated function code
2. Run manually in Azure Portal
3. Check Application Insights logs for "Successfully authenticated as GitHub App"

## Troubleshooting

### "Bad credentials" error
- Verify App ID is correct
- Check private key format (must include BEGIN/END markers)
- Ensure JWT is not expired (should be valid for 10 minutes)

### "Not Found" error
- Verify Installation ID is correct
- Check app is installed on the organization
- Ensure app has correct permissions

### "Integration suspended" error
- App was suspended by GitHub
- Go to app settings and reactivate

### Private key parsing issues
- If newlines cause issues, use base64 encoding
- Ensure entire key including headers is copied
- Check for extra whitespace or characters

## Security Best Practices

1. ✅ **Use Key Vault** for storing private keys (Option 3 above)
2. ✅ **Rotate keys regularly** (generate new private key every 6-12 months)
3. ✅ **Minimal permissions** (only request what's needed)
4. ✅ **Monitor app activity** in GitHub audit log
5. ✅ **Revoke unused tokens** (installation tokens auto-expire after 1 hour)

## Rate Limits

With GitHub App authentication:
- **5,000 requests per hour per installation**
- Much higher than PAT (5,000 per user account)
- Suitable for large organizations with 1000+ repositories

## Monitoring

View your app's activity:
- Organization audit log: `https://github.com/organizations/thefoggi/settings/audit-log`
- Filter by: `action:integration`

## Migration from PAT

If you're migrating from Personal Access Token:

1. Create and configure GitHub App (steps above)
2. Test in staging environment first
3. Update Azure Function App settings
4. Deploy updated code
5. Verify successful authentication
6. Revoke old PAT from GitHub

## Additional Resources

- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [Authenticating with a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app)
- [GitHub Apps vs OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)
