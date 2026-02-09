# Guia Técnico de Implementação de DORA Metrics

## Visão Geral

Este documento é um guia técnico passo-a-passo para implementar as quatro métricas DORA em ambientes GitHub Enterprise usando Azure Functions, Azure SQL Database e Power BI.

**Arquitetura:**
- **Coleta**: Azure Functions com triggers timer (a cada 5 minutos)
- **Autenticação**: GitHub App + Managed Identity do Azure
- **Armazenamento**: Azure SQL Database
- **Visualização**: Power BI (ou Grafana)

**O que são DORA Metrics:**
1. **Deployment Frequency** - Frequência de deployments em produção
2. **Lead Time for Changes** - Tempo do commit até produção  
3. **Change Failure Rate** - % de deployments que causam falhas
4. **Time to Restore Service** - Tempo médio de recuperação (MTTR)

**Tempo estimado total:** 4-6 horas

---

## Pré-requisitos

### Ferramentas Necessárias
```bash
# Instale antes de começar:
- Azure CLI (az)
- Azure Functions Core Tools (func)
- Python 3.9+
- Git
- sqlcmd (opcional) ou Azure Data Studio
```

### Permissões Necessárias
- **GitHub**: Permissão de admin na organização para criar GitHub Apps
- **Azure**: Contributor na subscription para criar recursos

### Verificação Inicial
```bash
# Verifique as instalações
az --version
func --version
python --version
git --version
```

---

## PARTE 1: Setup Inicial do Ambiente

### Passo 1.1: Clone o Repositório

```bash
# Clone este repositório
git clone <repository-url>
cd "DORA Metrics"
```

### Passo 1.2: Login no Azure

```bash
# Faça login no Azure
az login

# Configure a subscription correta
az account set --subscription "Your-Subscription-Name"

# Verifique
az account show
```

### Passo 1.3: Defina Variáveis de Ambiente

```bash
# Defina suas variáveis (ajuste os valores)
export RESOURCE_GROUP="dora-metrics-rg"
export LOCATION="eastus"
export SQL_SERVER_NAME="sql-dora-metrics-$(whoami)"
export SQL_DATABASE="sqldb-dora-metrics"
export FUNCTION_APP_NAME="func-dora-metrics-$(whoami)"
export STORAGE_ACCOUNT="stdorametrics$(whoami | tr -d '-')"
export GITHUB_ORG="your-github-org"

# SQL Admin (use um password seguro)
export SQL_ADMIN_USER="sqladmin"
export SQL_ADMIN_PASSWORD="YourSecurePassword123!"
```

### Passo 1.4: Crie o Resource Group

```bash
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### Passo 1.5: Crie o Azure SQL Server e Database

```bash
# Crie o SQL Server
az sql server create \
  --name $SQL_SERVER_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --admin-user $SQL_ADMIN_USER \
  --admin-password $SQL_ADMIN_PASSWORD

# Habilite acesso do Azure Services
az sql server firewall-rule create \
  --resource-group $RESOURCE_GROUP \
  --server $SQL_SERVER_NAME \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Adicione seu IP atual
MY_IP=$(curl -s ifconfig.me)
az sql server firewall-rule create \
  --resource-group $RESOURCE_GROUP \
  --server $SQL_SERVER_NAME \
  --name AllowMyIP \
  --start-ip-address $MY_IP \
  --end-ip-address $MY_IP

# Crie o Database
az sql db create \
  --resource-group $RESOURCE_GROUP \
  --server $SQL_SERVER_NAME \
  --name $SQL_DATABASE \
  --edition Basic \
  --compute-model Serverless \
  --family Gen5 \
  --capacity 2

# Habilite Entra ID (AAD) Authentication
az sql server ad-admin create \
  --resource-group $RESOURCE_GROUP \
  --server-name $SQL_SERVER_NAME \
  --display-name "Your Name" \
  --object-id $(az ad signed-in-user show --query id -o tsv)
```

### Passo 1.6: Crie o Storage Account

```bash
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS
```

### Passo 1.7: Crie o Function App

```bash
az functionapp create \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --os-type Linux \
  --assign-identity [system]

# Capture o Managed Identity Principal ID
FUNCTION_IDENTITY=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

echo "Function App Managed Identity: $FUNCTION_IDENTITY"
```

---

## PARTE 2: Configurar GitHub App

### Passo 2.1: Crie o GitHub App

1. Acesse: `https://github.com/organizations/YOUR-ORG/settings/apps`
2. Clique **"New GitHub App"**
3. Preencha:
   - **Name**: `DORA Metrics Collector`
   - **Homepage URL**: `https://github.com/YOUR-ORG`
   - **Webhook**: Desmarque "Active"

### Passo 2.2: Configure Permissões

**Repository permissions:**
- **Actions**: Read-only
- **Deployments**: Read-only  
- **Issues**: Read-only
- **Pull requests**: Read-only
- **Metadata**: Read-only (automático)

**Organization permissions:**
- **Members**: Read-only (opcional)

### Passo 2.3: Crie e Salve

1. Clique **"Create GitHub App"**
2. Anote o **App ID** (você verá na página)
3. Clique **"Generate a private key"**
4. Salve o arquivo `.pem` baixado

### Passo 2.4: Instale o App na Organização

1. Na página do app, clique **"Install App"**
2. Selecione sua organização
3. Escolha **"All repositories"** ou selecione repositórios específicos
4. Clique **"Install"**
5. Anote o **Installation ID** da URL: `https://github.com/organizations/YOUR-ORG/settings/installations/INSTALLATION_ID`

### Passo 2.5: Configure no Azure Function App

```bash
# Leia a private key
PRIVATE_KEY=$(cat ~/Downloads/your-app.*.private-key.pem)

# Configure as variáveis
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    "GITHUB_ORG_NAME=$GITHUB_ORG" \
    "GITHUB_APP_ID=123456" \
    "GITHUB_APP_INSTALLATION_ID=12345678" \
    "GITHUB_APP_PRIVATE_KEY=$PRIVATE_KEY" \
    "SQL_SERVER=${SQL_SERVER_NAME}.database.windows.net" \
    "SQL_DATABASE=$SQL_DATABASE" \
    "GITHUB_DEPLOYMENT_ENVIRONMENTS=production,staging" \
    "BASE_BRANCH=main" \
    "PR_LOOKBACK_HOURS=48" \
    "INCIDENT_LOOKBACK_HOURS=24"
```

---

## PARTE 3: Configurar Database Schemas

### Passo 3.1: Deploy Schema de Deployment Frequency

```bash
# Conecte ao database
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i demos/frequency-deployment/sql/schema.sql

# Ou use Azure Data Studio e execute o conteúdo de:
# demos/frequency-deployment/sql/schema.sql
```

**Schema criado:**
- `deployments` - Deployments do GitHub
- `deployment_metrics_daily` - Agregações diárias  
- `repositories` - Metadados de repositórios

### Passo 3.2: Deploy Schema de Lead Time

```bash
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i demos/lead_time_for_changes/sql/schema.sql
```

**Schema criado:**
- `pull_requests` - PRs mergeados com timestamps

### Passo 3.3: Deploy Schema de Change Failure Rate

```bash
# Se já tiver deployments, rode a migração primeiro:
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i demos/change_failure_rate/sql/migrate-add-product.sql

# Agora crie a tabela de incidents
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i demos/change_failure_rate/sql/schema.sql
```

**Schema criado:**
- `incidents` - GitHub Issues marcadas como incidents
- `product` column adicionada à tabela `deployments`

### Passo 3.4: Grant Permissions para o Function App

```bash
# No Azure Portal Query Editor ou via sqlcmd, execute:
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -Q "CREATE USER [${FUNCTION_APP_NAME}] FROM EXTERNAL PROVIDER; \
      ALTER ROLE db_datawriter ADD MEMBER [${FUNCTION_APP_NAME}]; \
      ALTER ROLE db_datareader ADD MEMBER [${FUNCTION_APP_NAME}];"
```

---

## PARTE 4: Deploy das Azure Functions

### Passo 4.1: Prepare o Ambiente Local

```bash
cd demos/frequency-deployment

# Crie virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Instale dependências
pip install -r requirements.txt
```

### Passo 4.2: Configure local.settings.json (opcional - para testes locais)

```bash
cat > local.settings.json << EOF
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "GITHUB_ORG_NAME": "$GITHUB_ORG",
    "GITHUB_APP_ID": "123456",
    "GITHUB_APP_INSTALLATION_ID": "12345678",
    "GITHUB_APP_PRIVATE_KEY": "$(cat ~/Downloads/your-app.*.private-key.pem)",
    "SQL_SERVER": "${SQL_SERVER_NAME}.database.windows.net",
    "SQL_DATABASE": "$SQL_DATABASE",
    "GITHUB_DEPLOYMENT_ENVIRONMENTS": "production,staging",
    "BASE_BRANCH": "main",
    "PR_LOOKBACK_HOURS": "48",
    "INCIDENT_LOOKBACK_HOURS": "24"
  }
}
EOF
```

### Passo 4.3: Teste Localmente (opcional)

```bash
# Inicie o function host
func start

# Você verá as 3 functions:
# - deployment_frequency_collector
# - lead_time_collector  
# - incident_collector

# Pressione Ctrl+C para parar
```

### Passo 4.4: Deploy para Azure

```bash
# Deploy da function app
func azure functionapp publish $FUNCTION_APP_NAME

# Aguarde o deploy completar (1-2 minutos)
```

### Passo 4.5: Verifique o Deploy

```bash
# Liste as functions
az functionapp function list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table

# Veja os logs em tempo real
az webapp log tail \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

---

## PARTE 5: Configuração dos Repositórios GitHub

### Passo 5.1: Configure GitHub Actions Workflows

Para rastrear deployments, adicione aos seus workflows do GitHub Actions:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # ← IMPORTANTE: define o environment
    
    steps:
      - uses: actions/checkout@v3
      
      # ... seus steps de build/test ...
      
      - name: Deploy
        run: |
          # Seu código de deploy aqui
          echo "Deploying to production..."
          
      # ← O GitHub cria um deployment event automaticamente
      # quando usa "environment: production"
```

**Pontos importantes:**
- Use `environment: production` ou `environment: staging` no job
- O GitHub cria deployment events automaticamente
- Não precisa de steps adicionais para DORA

### Passo 5.2: Configure Labels para Incidents

Crie labels nos repositórios:

1. Acesse: `https://github.com/YOUR-ORG/YOUR-REPO/labels`
2. Crie estas labels:
   - `incident` (cor: vermelho)
   - `production` (cor: laranja)

### Passo 5.3: Configure Issue Form para Incidents (opcional mas recomendado)

Crie `.github/ISSUE_TEMPLATE/incident.yml`:

```yaml
name: Production Incident
description: Report a production incident
title: "[INCIDENT] "
labels: ["incident", "production"]
body:
  - type: dropdown
    id: product
    attributes:
      label: Product
      description: Which product is affected?
      options:
        - MyApp
        - ServiceApp
        - OtherApp
    validations:
      required: true
      
  - type: dropdown
    id: severity
    attributes:
      label: Severity
      options:
        - Critical (P0)
        - High (P1)
        - Medium (P2)
        - Low (P3)
    validations:
      required: true
      
  - type: textarea
    id: description
    attributes:
      label: Description
      description: Describe the incident
    validations:
      required: true
```

---

## PARTE 6: Verificação e Testes

### Passo 6.1: Verifique Coleta de Deployments

```sql
-- Conecte ao SQL Database e execute:

-- Veja deployments coletados
SELECT TOP 10 
    repository,
    environment,
    commit_sha,
    created_at,
    status,
    collected_at
FROM deployments
ORDER BY created_at DESC;

-- Count por repositório
SELECT 
    repository,
    environment,
    COUNT(*) as total_deployments
FROM deployments
GROUP BY repository, environment
ORDER BY total_deployments DESC;
```

### Passo 6.2: Verifique Coleta de Pull Requests

```sql
-- Veja PRs coletados
SELECT TOP 10
    repository,
    pr_number,
    title,
    author,
    created_at,
    merged_at,
    merge_commit_sha
FROM pull_requests
ORDER BY merged_at DESC;

-- PRs que linkaram com deployments
SELECT 
    pr.repository,
    pr.pr_number,
    pr.created_at as pr_created,
    d.created_at as deployed,
    DATEDIFF(MINUTE, pr.created_at, d.created_at) as lead_time_minutes
FROM pull_requests pr
INNER JOIN deployments d ON pr.merge_commit_sha = d.commit_sha
WHERE d.environment = 'production'
ORDER BY d.created_at DESC;
```

### Passo 6.3: Verifique Coleta de Incidents

```sql
-- Veja incidents coletados
SELECT TOP 10
    repository,
    issue_number,
    title,
    product,
    state,
    created_at,
    closed_at
FROM incidents
ORDER BY created_at DESC;

-- Incidents vinculados a deployments (janela de 24h)
SELECT 
    d.repository,
    d.created_at as deployment_time,
    i.issue_number,
    i.title as incident_title,
    i.created_at as incident_time,
    DATEDIFF(HOUR, d.created_at, i.created_at) as hours_after_deploy
FROM deployments d
LEFT JOIN incidents i 
    ON d.repository = i.repository
    AND i.created_at >= d.created_at
    AND i.created_at <= DATEADD(HOUR, 24, d.created_at)
WHERE d.environment = 'production'
ORDER BY d.created_at DESC;
```

### Passo 6.4: Force Trigger das Functions (teste manual)

```bash
# No Azure Portal:
# 1. Vá para Function App → Functions
# 2. Clique em "deployment_frequency_collector"
# 3. Clique "Test/Run" → "Run"
# 4. Veja os logs

# Ou via Azure CLI (aguarda completar):
az functionapp function show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --function-name deployment_frequency_collector
```

---

## PARTE 7: Configurar Power BI Dashboard (DETALHADO)

### Passo 7.1: Conecte Power BI ao SQL Database

1. Abra **Power BI Desktop**
2. **Home** → **Get Data** → **Azure** → **Azure SQL Database**
3. Preencha a conexão:
   - **Server**: `sql-dora-metrics-yourname.database.windows.net`
   - **Database**: `sqldb-dora-metrics`
4. Clique **OK**
5. Em **Authentication**, selecione:
   - **Microsoft account** (para usar Entra ID)
   - Clique **Sign in** e autentique
6. Clique **Connect**
7. Na janela **Navigator**, selecione as tabelas:
   - ☑ `deployments`
   - ☑ `pull_requests`
   - ☑ `incidents`
   - ☑ `repositories`
8. Clique **Load** (não Transform por enquanto)

### Passo 7.2: Configure o Modelo de Dados

#### A. Crie Relacionamento entre Pull Requests e Deployments

1. Vá para **Model View** (ícone de tabelas à esquerda)
2. Crie o relacionamento principal:

**Pull Requests → Deployments**
- Arraste `pull_requests[merge_commit_sha]` para `deployments[commit_sha]`
- **Cardinality**: Many to One (*:1)
- **Cross filter direction**: Both
- **Make this relationship active**: ✓

Este é o relacionamento essencial para calcular o **Lead Time for Changes**.

**Nota**: O relacionamento Deployments ↔ Incidents é time-based (janela de 24h), então será feito via tabela calculada DAX.

### Passo 7.3: Crie Tabela de Relacionamento Deployment-Incident

Para correlacionar deployments com incidents (janela de 24h), crie uma tabela calculada:

**Modeling** → **New Table**

```dax
DeploymentIncidents = 
VAR ProductionDeployments = 
    SELECTCOLUMNS(
        FILTER(deployments, deployments[environment] = "production"),
        "deployment_id", deployments[id],
        "deployment_created_at", deployments[created_at],
        "deployment_repository", deployments[repository],
        "deployment_environment", deployments[environment],
        "deployment_commit_sha", deployments[commit_sha]
    )
VAR ClosedIncidents = 
    SELECTCOLUMNS(
        FILTER(incidents, NOT(ISBLANK(incidents[closed_at]))),
        "incident_id", incidents[id],
        "incident_issue_number", incidents[issue_number],
        "incident_created_at", incidents[created_at],
        "incident_closed_at", incidents[closed_at],
        "incident_repository", incidents[repository],
        "product", incidents[product],
        "incident_url", incidents[url],
        "incident_title", incidents[title]
    )
RETURN
FILTER(
    ADDCOLUMNS(
        CROSSJOIN(ProductionDeployments, ClosedIncidents),
        "detection_lag_hours", 
            DATEDIFF([deployment_created_at], [incident_created_at], HOUR),
        "traditional_mttr_hours", 
            DATEDIFF([incident_created_at], [incident_closed_at], HOUR),
        "deployment_mttr_hours", 
            DATEDIFF([deployment_created_at], [incident_closed_at], HOUR)
    ),
    [deployment_repository] = [incident_repository] &&
    [incident_created_at] >= [deployment_created_at] &&
    [detection_lag_hours] <= 24 &&
    [traditional_mttr_hours] >= 0
)
```

### Passo 7.4: Crie a Coluna Calculada Lead Time

Antes de criar medidas, adicione uma coluna calculada na tabela `deployments`:

**Clique na tabela `deployments`** → **Modeling** → **New Column**

```dax
Lead Time (Hours) = 
VAR PRCreatedTime = 
    CALCULATE(
        MAX(pull_requests[created_at]),
        FILTER(
            pull_requests,
            pull_requests[merge_commit_sha] = deployments[commit_sha]
        )
    )
RETURN
    IF(
        NOT ISBLANK(PRCreatedTime) && deployments[status] = "SUCCESS",
        DIVIDE(
            DATEDIFF(PRCreatedTime, deployments[created_at], MINUTE),
            60,
            BLANK()
        ),
        BLANK()
    )
```

Esta coluna calcula o lead time para cada deployment individualmente.

### Passo 7.5: Crie Todas as Medidas DAX

Crie uma pasta de medidas: **Home** → **Enter Data** → Nome: "_Measures" (tabela vazia)

**Modeling** → **New Measure** (dentro da tabela `_Measures`)

#### Medidas - DEPLOYMENT FREQUENCY

```dax
Total Deployments = 
COUNTROWS(deployments)
```

```dax
Total Incidents = 
COUNTROWS(incidents)
```

#### Medidas - LEAD TIME FOR CHANGES

```dax
Median Lead Time (Hours) = 
PERCENTILE.INC(
    deployments[Lead Time (Hours)],
    0.5
)
```

```dax
Average Lead Time (Hours) = 
AVERAGE(deployments[Lead Time (Hours)])
```

```dax
DORA Performance = 
VAR MedianHours = [Median Lead Time (Hours)]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(MedianHours), "No Data",
        MedianHours < 24, "🏆 Elite",
        MedianHours < 168, "⭐ High",
        MedianHours < 720, "📊 Medium",
        "📉 Low"
    )
```

#### Medidas - CHANGE FAILURE RATE

```dax
Deployments With Incidents = 
VAR IncidentsWithDeployment = 
    ADDCOLUMNS(
        incidents,
        "LinkedDeploymentID",
        CALCULATE(
            MAX(deployments[id]),
            FILTER(
                ALL(deployments),
                deployments[repository] = incidents[repository]
                && deployments[created_at] <= incidents[created_at]
                && incidents[created_at] <= deployments[created_at] + 1
            )
        )
    )
VAR UniqueDeploymentsWithIncidents = 
    DISTINCT(
        SELECTCOLUMNS(
            FILTER(
                IncidentsWithDeployment,
                NOT(ISBLANK([LinkedDeploymentID]))
            ),
            "DeploymentID", [LinkedDeploymentID]
        )
    )
RETURN
    COUNTROWS(UniqueDeploymentsWithIncidents)
```

```dax
CFR % = 
DIVIDE(
    [Deployments With Incidents],
    [Total Deployments],
    0
) * 100
```

```dax
CFR Category = 
VAR CFRValue = [CFR %]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(CFRValue), "No Data",
        CFRValue <= 5, "Elite (0-5%)",
        CFRValue <= 10, "High (5-10%)",
        CFRValue <= 15, "Medium (10-15%)",
        "Low (>15%)"
    )
```

```dax
CFR Color = 
VAR CFRValue = [CFR %]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(CFRValue), "#CCCCCC",
        CFRValue <= 5, "#28A745",      // Green - Elite
        CFRValue <= 10, "#17A2B8",     // Blue - High
        CFRValue <= 15, "#FFC107",     // Yellow - Medium
        "#DC3545"                      // Red - Low
    )
```

#### Medidas - TIME TO RESTORE SERVICE (MTTR)

```dax
Traditional MTTR - Mean (Hours) = 
AVERAGEX(
    FILTER(incidents, NOT(ISBLANK(incidents[closed_at]))),
    DATEDIFF(incidents[created_at], incidents[closed_at], HOUR)
)
```

```dax
Traditional MTTR - Median (Hours) = 
PERCENTILEX.INC(
    FILTER(incidents, NOT(ISBLANK(incidents[closed_at]))),
    DATEDIFF(incidents[created_at], incidents[closed_at], HOUR),
    0.5
)
```

```dax
Deployment MTTR - Mean (Hours) = 
AVERAGE(DeploymentIncidents[deployment_mttr_hours])
```

```dax
Deployment MTTR - Median (Hours) = 
PERCENTILEX.INC(
    DeploymentIncidents,
    [deployment_mttr_hours],
    0.5
)
```

```dax
Detection Lag - Median (Hours) = 
PERCENTILEX.INC(
    DeploymentIncidents,
    [detection_lag_hours],
    0.5
)
```

```dax
Closed Incidents Count = 
COUNTROWS(
    FILTER(incidents, NOT(ISBLANK(incidents[closed_at])))
)
```

```dax
Deployments with Closed Incidents = 
DISTINCTCOUNT(DeploymentIncidents[deployment_id])
```

```dax
DORA Tier - Traditional MTTR = 
VAR MedianMTTR = [Traditional MTTR - Median (Hours)]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(MedianMTTR), "No Data",
        MedianMTTR < 1, "Elite",
        MedianMTTR < 24, "High",
        MedianMTTR < 168, "Medium",
        "Low"
    )
```

### Passo 7.6: Crie os Visuais - Página 1: Deployment Frequency

#### Layout da Página:
```
+------------------+------------------+
| Card 1           | Card 2           |
| Total Deploy     | Total Incidents  |
+------------------+------------------+
| Line Chart: Deployments Over Time  |
|                                     |
+-------------------------------------+
| Bar Chart: Deploy by Repo          |
|                                     |
+-------------------------------------+
| Bar Chart: Deploy by Environment   |
+-------------------------------------+
```

#### Visual 1: Card - Total Deployments

1. **Insert** → **Card**
2. Arraste para o campo **Fields**:
   - `_Measures[Total Deployments]`
3. **Format** → **Callout value**:
   - **Font**: Segoe UI, Bold, 48pt
   - **Color**: #1F2937
4. **Format** → **Category label**:
   - **Text**: "Total Deployments"
   - **Font**: 14pt
   - **Color**: #6B7280
5. Posicione no canto superior esquerdo

#### Visual 2: Card - Deployments Per Day

1. **Insert** → **Card**
2. **Fields**: `_Measures[Deployments Per Day]`
3. **Format** → **Callout value**:
   - Formato: Number, 2 decimals
4. Posicione ao lado do Card 1

#### Visual 3: Card - MoM Change %

1. **Insert** → **Card**
2. **Fields**: `_Measures[Deployments MoM Change %]`
3. **Format** → **Callout value**:
   - Formato: Percentage, 1 decimal
   - Conditional formatting: Verde se >0, Vermelho se <0
4. Posicione ao lado do Card 2

#### Visual 4: Line Chart - Deployments Over Time

1. **Insert** → **Line Chart**
2. Configure campos:
   - **X-axis**: `deployments[created_at]` (hierarquia: Year → Month → Day)
   - **Y-axis**: `_Measures[Total Deployments]`
   - **Legend**: `deployments[environment]`
3. **Format** → **X-axis**:
   - **Type**: Continuous
   - **Title**: "Date"
4. **Format** → **Y-axis**:
   - **Title**: "Number of Deployments"
5. **Format** → **Data colors**:
   - production: #10B981 (verde)
   - staging: #3B82F6 Total Incidents

1. **Insert** → **Card**
2. **Fields**: `_Measures[Total Incidents]`
3. **Format** → **Callout value**:
   - **Font**: Segoe UI, Bold, 48pt
   - **Color**: #DC3545 (vermelho)
4. **Format** → **Category label**:
   - **Text**: "Total Incidents"
5. Posicione ao lado do Card 1
#### Visual 6: Bar Chart - Deployments by Environment

1. **Insert** → **Clustered Column Chart**
2. Configure:
   - **X-axis**: `deployments[environment]`
   - **Y-axis**: `_Measures[Total Deployments]`
3. **Format** → **Data colors**: Mesmas cores do Line Chart
4. **Format** → **Data labels**: On
5. Posicione ao lado do Bar Chart (metade direita)

#### Visual 7: Slicer - Date Range

1. **Insert** → **Slicer**
2. **Field**: `deployments[created_at]`
3. **Slicer settings** → **Style**: Between
4. Posicione no topo da página

#### Visual 8: Slicer - Repository

1. **Insert** → **Slicer**
2. **Field**: `deployments[repository]`
3. **Slicer settings** → **Style**: Dropdown
4. **Selection**: Multi-select with Ctrl
5. Posicione ao lado do Date Slicer

### Passo 7.7: Crie os Visuais - Página 2: Lead Time for Changes

#### Layout:
```
+------------------+------------------+------------------+
| Card: Median LT  | Card: Average LT | Card: Performance|
+------------------+------------------+------------------+
| Line Chart: Lead Time Trend                           |
|                                                        |
+--------------------------------------------------------+
| Scatter Plot: Lead Time Distribution                  |
|                                                        |
+--------------------------------------------------------+
| Table: Top 10 Longest Lead Times                      |
+--------------------------------------------------------+
```

#### Visual 1-3: Cards - Lead Time Metrics

**Card 1: Median Lead Time**
1. **Insert** → **Card**
2. **Fields**: `_Measures[Median Lead Time (Hours)]`
3. **Format** → **Callout value**: 2 decimals
4. Adicione texto "Median Lead Time (Hours)"

**Card 2: Average Lead Time**
1. **Insert** → **Card**
2. **Fields**: `_Measures[Average Lead Time (Hours)]`
3. **Format**: Similar ao Card 1

**Card 3: DORA Performance**
1. **Insert** → **Card**
2. **Fields**: `_Measures[DORA Performance]`
3. **Format** → **Callout value**:
   - Conditional formatting baseado no valor:
     - Elite: Verde
     - High: Azul
     - Medium: Laranja
     - Low: Vermelho

#### Visual 4: Line Chart - Lead Time Trend

1. **Insert** → **Line Chart**
2. Configure:
   - **X-axis**: `deployments[created_at]` (agregado por Month)
   - **Y-axis**: `_Measures[Median Lead Time (Hours)]`
   - **Secondary Y-axis**: `_Measures[Average Lead Time (Hours)]`
3. **Format** → **Lines**:
   - Median: Linha sólida
   - Average: Linha pontilhada
4. Adicione **Analytics** → **Constant line** no valor 1 (Elite threshold)

#### Visual 5: Scatter Chart - Lead Time Distribution

**Importante**: Este requer uma tabela de fato com lead times individuais.

1. Primeiro, crie uma tabela calculada:

```dax
LeadTimeDetails = 
1. **Insert** → **Scatter Chart**
2. Configure:
   - **X-axis**: `deployments[created_at]`
   - **Y-axis**: `deployments[Lead Time (Hours)]`
   - **Legend**: `deployments[repository]`
   - **Size**: (deixe vazio ou use count)
3. **Filters**: Adicione filtro para `deployments[Lead Time (Hours)]` is not blank

#### Visual 6: Table - Top 10 Longest Lead Times

1. **Insert** → **Table**
2. Configure colunas:
   - `deployments[repository]`
   - `deployments[commit_sha]`
   - `deployments[created_at]`
   - `deployments[Lead Time (Hours)]`
3. **Format** → **Values**:
   - Lead Time: Conditional formatting (vermelho para >168h)
4. **Filters**: Top 10 por Lead Time (Hours), Descending-----------------+
| Card: CFR %      | Card: Category   | Card: Total      |
|                  |                  | Deployments      |
+------------------+------------------+------------------+
| Card: Deploy     | Card: Total      |                  |
| w/ Incidents     | Incidents        |                  |
+------------------+------------------+------------------+
| Line Chart: CFR Trend Over Time                       |
|                                                        |
+--------------------------------------------------------+
| Bar Chart: CFR by Repository                          |
+--------------------------------------------------------+
| Table: Recent Incidents with Deployments              |
+--------------------------------------------------------+
```

#### Visual 1-5: Cards - CFR Metrics

**Card 1: CFR %**
1. **Insert** → **Card**
2. **Fields**: `_Measures[CFR %]`
3. **Format** → **Callout value**:
   - Formato: 2 decimals + "%"
   - Conditional formatting baseado em `_Measures[CFR Color]`

**Card 2: CFR Category**
1. **Insert** → **Card**
2. **Fields**: `_Measures[CFR Category]`

**Card 3: Total Deployments**
1. **Card** com `_Measures[Production Deployments]`

**Card 4: Deployments with Incidents**
1. **Card** com `_Measures[Deployments With Incidents]`

**Card 5: Total Incidents**
1. **Card** com `_Measures[Total Incidents]`

#### Visual 6: Line Chart - CFR Trend

1. **Insert** → **Line and Stacked Column Chart**
2. Configure:
   - **Shared axis**: `deployments[created_at]` (agregado por Month)
   - **Column values**: `_Measures[Production Deployments]`
   - **Line values**: `_Measures[CFR %]`
3. **Format** → **Y-axis** (linha):
   - **Title**: "CFR %"
   - **Min**: 0, **Max**: 100
4. **Format** → **Secondary Y-axis** (coluna):
   - **Title**: "Deployments"
5. Adicione **Constant line** em 15% (Elite threshold)

#### Visual 7: Clustered Bar Chart - CFR by Repository

1. **Insert** → **Clustered Bar Chart**
2. Configure:
   - **Y-axis**: `DeploymentIncidents[deployment_repository]`
   - **X-axis (1)**: `_Measures[Production Deployments]`
   - **X-axis (2)**: `_Measures[Deployments With Incidents]`
3. **Format** → **Data colors**:
   - Deployments: Azul clarTotal
   - With Incidents: Vermelho
4. **Format** → **Data labels**: On

#### Visual 8: Table - Recent Incidents

1. **Insert** → **Table**
2. Configure colunas:Total
   - `DeploymentIncidents[incident_issue_number]`
   - `DeploymentIncidents[incident_title]`
   - `DeploymentIncidents[product]`
   - `DeploymentIncidents[deployment_repository]`
   - `DeploymentIncidents[deployment_created_at]`
   - `DeploymentIncidents[incident_created_at]`
   - `DeploymentIncidents[detection_lag_hours]`
3. **Format** → **Style**: Minimal
4. **Filters** → **incident_created_at**: Last 30 days
5. **Sort**: Por incident_created_at, Descending

### Passo 7.9: Crie os Visuais - Página 4: Time to Recovery

#### Layout:Total
```
+------------------+------------------+------------------+
| Card: Trad MTTR  | Card: Deploy     | Card: Detection  |
| Median           | MTTR Median      | Lag Median       |
+------------------+------------------+------------------+
| Card: Closed     | Card: DORA Tier  |                  |
| Incidents        |                  |                  |
+------------------+------------------+------------------+
| Combo Chart: MTTR Comparison Over Time               |
|                                                        |
+--------------------------------------------------------+
| Clustered Bar: MTTR by Product                        |
|                                                        |
+--------------------------------------------------------+
| Table: Incident Details with Resolution Times         |
+--------------------------------------------------------+
```

#### Visual 1-5: Cards - MTTR Metrics

**Card 1: Traditional MTTR - Median**
1. **Card** com `_Measures[Traditional MTTR - Median (Hours)]`
2. **Format**: 2 decimals

**Card 2: Deployment MTTR - Median**
1. **Card** com `_Measures[Deployment MTTR - Median (Hours)]`

**Card 3: Detection Lag - Median**
1. **Card** com `_Measures[Detection Lag - Median (Hours)]`

**Card 4: Closed Incidents Count**
1. **Card** com `_Measures[Closed Incidents Count]`

**Card 5: DORA Tier**
1. **Card** com `_Measures[DORA Tier - Traditional MTTR]`
2. Conditional formatting por tier

#### Visual 6: Line Chart - MTTR Trends

1. **Insert** → **Line Chart**
2. Configure:
   - **X-axis**: `incidents[created_at]` (agregado por Month)
   - **Y-axis (múltiplas linhas)**:
     - `_Measures[Traditional MTTR - Median (Hours)]`
     - `_Measures[Deployment MTTR - Median (Hours)]`
3. **Format** → **Lines**:
   - Traditional: Azul claro (#3B82F6)
   - Deployment: Azul escuro (#1E40AF)
4. **Analytics** → **Constant lines**:
   - 1 hora (Elite)
   - 24 horas (High)

#### Visual 7: Clustered Bar Chart - MTTR by Product

1. **Insert** → **Clustered Bar Chart**
2. Configure:
   - **Y-axis**: `DeploymentIncidents[product]`
   - **X-axis**: 
     - `_Measures[Traditional MTTR - Median (Hours)]`
     - `_Measures[Deployment MTTR - Median (Hours)]`
3. **Format** → **Data labels**: On
4. **Sort**: Por Traditional MTTR, Descending

#### Visual 8: Table - Incident Details

1. **Insert** → **Table**
2. Configure colunas:
   - `DeploymentIncidents[incident_issue_number]` (como link)
   - `DeploymentIncidents[incident_title]`
   - `DeploymentIncidents[deployment_repository]`
   - `DeploymentIncidents[product]`
   - `DeploymentIncidents[incident_created_at]`
   - `DeploymentIncidents[incident_closed_at]`
   - `DeploymentIncidents[traditional_mttr_hours]`
   - `DeploymentIncidents[deployment_mttr_hours]`
3. **Format** → **URL icon**: On para incident_url
4. **Format** → **Conditional formatting** em MTTR:
   - Verde: <1h
   - Azul: 1-24h
   - Laranja: 24-168h
   - Vermelho: >168h

### Passo 7.10: Configure Filtros Globais e Interações

#### Adicione Slicers em Todas as Páginas:

1. **Date Range Slicer**:
   - **Insert** → **Slicer**
   - **Field**: `deployments[created_at]`
   - **Style**: Between
   - **Sync slicers**: Ative para todas as páginas

2. **Repository Slicer**:
   - **Field**: `deployments[repository]`
   - **Style**: Dropdown, Multi-select
   - **Sync slicers**: Ative para todas as páginas

3. **Environment Slicer**:
   - **Field**: `deployments[environment]`
   - **Style**: Checkbox
   - **Default**: production (selecionado)

#### Configure Interações entre Visuais:

1. Vá para **Format** → **Edit interactions**
2. Para cada página:
   - Line charts: Filtram outros visuais
   - Cards: Não filtram (desabilite interactions)
   - Slicers: Filtram todos os visuais
   - Tables: Highlight ao invés de filter

### Passo 7.11: Aplique Tema Personalizado

Crie ou use um tema JSON:

```json
{
  "name": "DORA Metrics Theme",
  "dataColors": [
    "#10B981", "#3B82F6", "#F59E0B", "#EF4444", 
    "#8B5CF6", "#14B8A6", "#F97316", "#EC4899"
  ],
  "background": "#FFFFFF",
  "foreground": "#1F2937",
  "tableAccent": "#3B82F6",
  "good": "#10B981",
  "neutral": "#F59E0B",
  "bad": "#EF4444"
}
```

**View** → **Themes** → **Browse for themes** → Selecione o JSON

### Passo 7.12: Publique e Configure Refresh

1. **File** → **Publish** → **Publish to Power BI**
2. Selecione seu workspace
3. No Power BI Service:
   - Navegue até o dataset
   - **Settings** → **Data source credentials**
   - Configure a autenticação (OAuth2)
4. **Scheduled refresh**:
   - **Refresh frequency**: Daily
   - **Time**: 2 AM, 6 AM, 10 AM, 2 PM, 6 PM, 10 PM
   - **Notify on failure**: ✓
   - **Send failure notification to**: seu-email@company.com

### Passo 7.13: Crie Alertas (Power BI Service)

1. Em cada Card importante, clique nos **⋯** → **Manage alerts**
2. Configure alertas:
   - **CFR > 30%**: Alerta vermelho
   - **Deployments Per Day < 1**: Alerta amarelo
   - **Median Lead Time > 168h**: Alerta laranja
   - **MTTR > 24h**: Alerta vermelho

### Passo 7.14: Compartilhe o Dashboard

1. **File** → **Publish to web** (se público)
2. Ou **Share** → Adicione usuários/grupos específicos
3. Configure permissões:
   - **Can reshare**: Apenas admins
   - **Can build content**: Apenas editors
   - **View only**: Todos os outros

---

## Notas sobre Power BI

### Otimização de Performance

- Use **DirectQuery** para dados ao vivo, **Import** para melhor performance
- Remova colunas não utilizadas nas tabelas
- Use agregações onde possível
- Limite o histórico de dados (ex: últimos 2 anos)

---

## PARTE 8: Monitoramento e Troubleshooting

### Monitor Function Execution

```bash
# Veja logs em tempo real
az webapp log tail \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP

# Veja executions recentes
az monitor activity-log list \
  --resource-group $RESOURCE_GROUP \
  --max-events 50
```

### Common Issues

**1. Function não executa:**
```bash
# Verifique o status
az functionapp show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query state

# Restart se necessário
az functionapp restart \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

**2. Erro de conexão SQL:**
```sql
-- Verifique se o managed identity tem permissões:
SELECT 
    dp.name as user_name,
    dp.type_desc,
    r.name as role_name
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'func-dora-metrics-yourname';
```

**3. GitHub API rate limit:**
```bash
# Verifique rate limit
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.github.com/rate_limit
```

### Alertas Recomendados

Configure no Azure Monitor:
- Function execution failures > 5 in 15 minutes
- SQL Database DTU > 80%
- Function execution time > 5 minutes

---

## PARTE 9: Time to Restore Service (MTTR)

> **Nota**: Esta métrica é calculada automaticamente a partir dos incidents coletados.

### Como Funciona

1. **Incident Creation**: GitHub Issue criada com labels `incident` + `production`
2. **Resolution**: Issue é fechada quando o problema é resolvido
3. **MTTR Calculation**: `closed_at - created_at` por incident
4. **Aggregation**: Mediana e média no Power BI

### Workflow Recomendado

```markdown
1. Incidente detectado → Crie GitHub Issue com template "incident"
2. Adicione labels: "incident" + "production"  
3. Investigue e resolva o problema
4. Feche a issue quando restaurado
5. MTTR automaticamente calculado
```

### Queries Úteis

```sql
-- MTTR por produto
SELECT 
    product,
    COUNT(*) as total_incidents,
    AVG(DATEDIFF(MINUTE, created_at, closed_at)) as avg_mttr_minutes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY DATEDIFF(MINUTE, created_at, closed_at)) 
        OVER (PARTITION BY product) as median_mttr_minutes
FROM incidents
WHERE closed_at IS NOT NULL
GROUP BY product;

-- Incidents ainda abertos
SELECT 
    repository,
    issue_number,
    title,
    product,
    created_at,
    DATEDIFF(HOUR, created_at, GETUTCDATE()) as hours_open
FROM incidents
WHERE state = 'open'
ORDER BY created_at;
```

---

## Troubleshooting Rápido

### Nenhum dado sendo coletado?

1. **Verifique GitHub App permissions**: Actions, Deployments, Issues, Pull Requests
2. **Force run**: Trigger manual no Azure Portal
3. **Veja logs**: `az webapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP`
4. **Verifique environment**: Workflows devem usar `environment: production`

### Deployments aparecem mas PRs não linkam?

1. **Verifique commit SHA**: `merge_commit_sha` deve corresponder ao `commit_sha` do deployment
2. **Lookback window**: Aumente `PR_LOOKBACK_HOURS` se necessário
3. **Base branch**: Confirme que está mergeando para o branch correto (geralmente `main`)

### Incidents não estão aparecendo?

1. **Verifique labels**: Issues devem ter AMBAS: `incident` E `production`
2. **Form template**: Use o issue form para consistência
3. **Lookback window**: Aumente `INCIDENT_LOOKBACK_HOURS` se necessário

---

## Manutenção e Evolução

### Adicionar Novos Repositórios

Automaticamente incluídos se:
- Repositório está na organização GitHub
- GitHub App está instalado no repositório
- Workflows usam `environment: production/staging`

### Adicionar Novos Produtos

1. Adicione à lista do issue form template
2. Nenhuma mudança no código necessário
3. Aparecerá automaticamente no Power BI

### Escalar para Múltiplas Organizações

```bash
# Crie uma function por org, ou:
# Configure variável com múltiplas orgs
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings "GITHUB_ORGS=org1,org2,org3"

# Atualize o código para iterar pelas orgs
```

### Backup do Database

```bash
# Configure automated backups
az sql db show \
  --resource-group $RESOURCE_GROUP \
  --server $SQL_SERVER_NAME \
  --name $SQL_DATABASE \
  --query earliestRestoreDate

# Retention automático: 7 dias (Basic tier)
```

---

## Benchmark DORA Levels

Use estas referências para avaliar sua performance:

| Métrica | Elite | High | Medium | Low |
|---------|-------|------|--------|-----|
| **Deployment Frequency** | Múltiplos por dia | 1x por semana a 1x por mês | 1x por mês a 1x a cada 6 meses | Menos de 1x a cada 6 meses |
| **Lead Time** | < 24 horas | 1 dia a 1 semana | 1 semana a 1 mês | > 1 mês |
| **Change Failure Rate** | 0-5% | 5-10% | 10-15% | > 15% |
| **Time to Restore** | < 1 hora | 1 hora a 1 dia | 1 dia a 1 semana | > 1 semana |

---

## Recursos Adicionais

- **Documentação**: Veja READMEs em `demos/*/README.md`
- **Schema Details**: Veja SQL files em `demos/*/sql/`
- **DORA Research**: https://dora.dev/
- **GitHub Actions**: https://docs.github.com/en/actions
- **Azure Functions**: https://learn.microsoft.com/azure/azure-functions/

---

## Suporte

Para dúvidas ou problemas:
1. Verifique os logs da function: `az webapp log tail`
2. Revise as queries SQL de troubleshooting
3. Consulte os READMEs específicos de cada métrica
4. Abra uma issue neste repositório
