# DORA Metrics com GitHub Enterprise, Azure Functions e Power BI

## Visão Geral

Este documento é um guia técnico passo-a-passo para implementar as quatro métricas DORA em ambientes GitHub Enterprise usando Azure Functions, Azure SQL Database e Power BI.

**Arquitetura:**
- **Coleta**: Azure Functions com triggers timer (a cada 5 minutos)
- **Autenticação**: GitHub App + Managed Identity do Azure
- **Armazenamento**: Azure SQL Database
- **Visualização**: Power BI

```
GitHub Org ──► Azure Function App ──► Azure SQL Database ──► PowerBI
               (Timer: every 5min)    (Entra ID auth)        (DirectQuery)
               ├─ deployment_frequency_collector → deployments table
               ├─ lead_time_collector            → pull_requests table
               └─ change_failure_rate_collector  → incidents table
```

**O que são DORA Metrics:**
1. **Deployment Frequency** - Frequência de deployments em produção
2. **Lead Time for Changes** - Tempo do commit até produção  
3. **Change Failure Rate** - % de deployments que causam falhas
4. **Time to Restore Service** - Tempo médio de recuperação (MTTR)

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

### Referência de Variáveis de Ambiente

| Variável | Descrição | Default | Obrigatória |
|----------|-----------|---------|-------------|
| `GITHUB_ORG_NAME` | Nome da organização GitHub | - | Sim |
| `GITHUB_APP_ID` | ID do GitHub App | - | Sim |
| `GITHUB_APP_INSTALLATION_ID` | ID da instalação do GitHub App | - | Sim |
| `GITHUB_APP_PRIVATE_KEY` | Chave privada do GitHub App (raw ou base64) | - | Sim |
| `GITHUB_DEPLOYMENT_ENVIRONMENTS` | Filtro de environments (separados por vírgula) | (todos) | Não |
| `BASE_BRANCH` | Branch a monitorar para PRs mergeados | `main` | Não |
| `PR_LOOKBACK_HOURS` | Horas de lookback para PRs mergeados | `48` | Não |
| `INCIDENT_LOOKBACK_HOURS` | Horas de lookback para incidents | `24` | Não |
| `SQL_SERVER` | FQDN do SQL Server | - | Sim |
| `SQL_DATABASE` | Nome do SQL Database | - | Sim |

---

## PARTE 3: Configurar Database Schemas

Todos os schemas estão consolidados em um único arquivo SQL.

### Passo 3.1: Deploy Schema Unificado

```bash
# Conecte ao database e execute o schema unificado
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i function_app/sql/schema.sql

# Ou use Azure Data Studio / Azure Portal Query Editor
# e execute o conteúdo de: function_app/sql/schema.sql
```

**Tabelas criadas:**
- `deployments` - Deployments do GitHub
- `deployment_metrics_daily` - Agregações diárias
- `repositories` - Metadados de repositórios (time, produto)
- `pull_requests` - PRs mergeados com timestamps
- `incidents` - GitHub Issues marcadas como incidents

**Views criadas:**
- `vw_cfr_analysis` - Deployments correlacionados com incidents (janela 24h)
- `vw_lead_time_analysis` - PRs vinculados a deployments com cálculo de lead time

### Passo 3.2: Conceder permissões para o Function App

```bash
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i function_app/sql/grant-permissions.sql

# Ou execute manualmente:
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -Q "CREATE USER [${FUNCTION_APP_NAME}] FROM EXTERNAL PROVIDER; \
      ALTER ROLE db_datawriter ADD MEMBER [${FUNCTION_APP_NAME}]; \
      ALTER ROLE db_datareader ADD MEMBER [${FUNCTION_APP_NAME}];"
```

### Passo 3.3: Verificar Deploy do Schema

```bash
sqlcmd -S ${SQL_SERVER_NAME}.database.windows.net \
  -d $SQL_DATABASE \
  -G \
  -i function_app/sql/verify-collection.sql
```

**Arquivos SQL disponíveis:**

| Arquivo | Finalidade |
|---------|------------|
| `function_app/sql/schema.sql` | Cria todas as tabelas e views para as 4 métricas DORA |
| `function_app/sql/grant-permissions.sql` | Concede acesso ao Managed Identity do Function App |
| `function_app/sql/verify-collection.sql` | Queries de verificação para todas as métricas |

---

## PARTE 4: Deploy das Azure Functions

### Passo 4.1: Prepare o Ambiente Local

```bash
cd function_app

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

---

## PARTE 7: Configurar Power BI Dashboard

> **💡 Template Pronto para Usar**: Um arquivo Power BI Desktop (.pbix) pré-configurado está disponível em `powerbi/DORA-Metrics-Template.pbix` com todos os modelos de dados, medidas DAX e visualizações já criados. 
> 
> **Salve seu próprio**: Após criar o dashboard completo, salve o arquivo `.pbix` no diretório `powerbi/` para que outros possam usá-lo. Veja instruções em `powerbi/PLACE_PBIX_FILE_HERE.md`.

### Passo 7.1: Use o Template Power BI

1. **Abra o arquivo template**:
   ```
   powerbi/DORA-Metrics-Template.pbix
   ```

2. **Abra no Power BI Desktop**
   - Clique duas vezes no arquivo `.pbix` ou
   - Abra Power BI Desktop → **File** → **Open** → Selecione o arquivo

### Passo 7.2: Atualize a Conexão com seu Database

1. **Home** → **Transform data** → **Data source settings**

2. Clique em **Change Source...**

3. Atualize os valores:
   - **Server**: `${SQL_SERVER_NAME}.database.windows.net`
   - **Database**: `${SQL_DATABASE}`
   
4. Clique **OK**

5. **Edit Permissions** → **Credentials**:
   - Selecione **Microsoft account**
   - Clique **Sign in** e autentique com sua conta Azure com permissão de acesso ao SQL
   - Clique **Save**

### Passo 7.3: Atualize os Dados

1. Na faixa de aviso amarela no topo, clique **Refresh now**

2. Ou clique **Home** → **Refresh**

3. Aguarde o carregamento dos dados (pode levar 30-60 segundos)

### Passo 7.4: Verifique os Dados

1. Navegue pelas 4 páginas do dashboard:
   - **Deployment Frequency** - Visualize deployments por tempo/repositório
   - **Lead Time for Changes** - Análise de tempo entre commit e produção
   - **Change Failure Rate** - Taxa de deployments com incidents
   - **Time to Restore** - MTTR e tempos de recuperação

2. Verifique se os dados aparecem corretamente nos visuais

3. Teste os filtros (Date Range, Repository, Environment)

### Passo 7.5: Publique no Power BI Service

1. **File** → **Publish** → **Publish to Power BI**

2. Selecione seu **Workspace** (ou crie um novo)

3. Clique **Select**

4. Aguarde a publicação completar

5. Clique **Open 'DORA-Metrics-Template.pbix' in Power BI**

---

## O que está incluído no Template

O arquivo `.pbix` já contém:

✓ **Modelo de dados** configurado:
  - Relacionamentos entre `deployments`, `pull_requests`, `incidents`
  - Tabela calculada `DeploymentIncidents` (janela 24h)
  - Coluna calculada `Lead Time (Hours)`

✓ **Medidas DAX** (28 medidas):
  - Deployment Frequency metrics
  - Lead Time metrics com performance tiers
  - Change Failure Rate com categorização
  - MTTR metrics (traditional + deployment-based)

✓ **4 Páginas de Dashboard**:
  - Cards, line charts, bar charts, tables
  - Slicers sincronizados (Date, Repository, Environment)
  - Formatação condicional e tema aplicado

✓ **Tema personalizado** aplicado

---

## Modelo de Dados do Power BI

### Data Sources

Conecte o Power BI ao Azure SQL Database:
- Server: `${SQL_SERVER_NAME}.database.windows.net`
- Database: `$SQL_DATABASE`
- Authentication: Microsoft Entra ID (Azure Active Directory)

Importe estas tabelas/views:
- `deployments`
- `pull_requests`
- `incidents`
- `vw_cfr_analysis` (dados pré-correlacionados de CFR)
- `vw_lead_time_analysis` (dados pré-correlacionados de lead time)

### Relacionamentos

- `pull_requests[merge_commit_sha]` → `deployments[commit_sha]` (Many-to-One)
- Não é necessário relacionamento físico entre `deployments` e `incidents` (correlacionados via DAX ou SQL view)

### Medidas DAX

#### Deployment Frequency
```dax
Daily Deployment Rate = 
  DIVIDE(
    COUNTROWS(deployments),
    DISTINCTCOUNT(deployments[created_at].[Date]),
    0
  )
```

#### Lead Time for Changes
```dax
Median Lead Time (Hours) = 
  DIVIDE(
    PERCENTILE.INC(
      SELECTCOLUMNS(
        FILTER(vw_lead_time_analysis, vw_lead_time_analysis[deployment_id] <> BLANK()),
        "LT", vw_lead_time_analysis[lead_time_minutes]
      ),
      [LT],
      0.5
    ),
    60,
    0
  )

Performance Level = 
  VAR MedianHours = [Median Lead Time (Hours)]
  RETURN SWITCH(
    TRUE(),
    MedianHours < 24, "Elite (<1 day)",
    MedianHours < 168, "High (1-7 days)",
    MedianHours < 720, "Medium (1 week-1 month)",
    "Low (>1 month)"
  )
```

#### Change Failure Rate
```dax
Deployments With Incidents = 
  CALCULATE(
    DISTINCTCOUNT(deployments[id]),
    FILTER(
      deployments,
      CALCULATE(
        COUNTROWS(
          FILTER(
            incidents,
            incidents[repository] = deployments[repository]
            && incidents[created_at] >= deployments[created_at]
            && incidents[created_at] <= deployments[created_at] + 1
          )
        )
      ) > 0
    )
  )

Total Deployments = DISTINCTCOUNT(deployments[id])

CFR % = DIVIDE([Deployments With Incidents], [Total Deployments], 0) * 100

CFR Category = 
  VAR CFRValue = [CFR %]
  RETURN SWITCH(
    TRUE(),
    CFRValue <= 5, "Elite (0-5%)",
    CFRValue <= 10, "High (5-10%)",
    CFRValue <= 15, "Medium (10-15%)",
    CFRValue > 15, "Low (>15%)",
    "No Data"
  )
```

#### Time to Restore Service
```dax
Median MTTR (Hours) = 
  DIVIDE(
    PERCENTILE.INC(
      SELECTCOLUMNS(
        FILTER(incidents, incidents[state] = "closed" && incidents[closed_at] <> BLANK()),
        "MTTR", DATEDIFF(incidents[created_at], incidents[closed_at], MINUTE)
      ),
      [MTTR],
      0.5
    ),
    60,
    0
  )
```

### Visualizações Recomendadas

**Página 1: Executive Dashboard**
- 4 KPI cards: Deployment Frequency, Lead Time, CFR %, MTTR
- Indicador de nível de performance DORA por métrica
- Linhas de tendência (semanal) para as 4 métricas

**Página 2: Deployment Frequency**
- Tendência de frequência de deploy (diário/semanal)
- Deployments por repositório (gráfico de barras)
- Deployments por environment (donut)
- Taxa de sucesso vs falha

**Página 3: Lead Time for Changes**
- Tendência de lead time (mediana semanal)
- Distribuição de lead time (histograma)
- Lead time por repositório
- Taxa de correlação PR-Deployment

**Página 4: Change Failure Rate**
- Tendência de CFR ao longo do tempo
- CFR por repositório
- CFR por produto (usando slicer `incidents[product]`)
- Tabela de detalhes de incidents

**Página 5: Time to Restore Service**
- Tendência de MTTR ao longo do tempo
- MTTR por repositório
- Incidents abertos vs fechados
- Timeline de resolução de incidents

**Slicers (todas as páginas):**
- Date range
- Repository (multi-select)
- Environment
- Product (from incidents)

---

## Personalizando o Dashboard

Se quiser modificar o template:

1. **Adicionar novos visuais**: **Insert** → Escolha o tipo de visual
2. **Modificar medidas DAX**: **Modeling** → Clique na medida → Edite na barra de fórmulas
3. **Alterar cores**: **Format** → **Data colors**
4. **Adicionar páginas**: Clique **+** no rodapé
5. **Ver instruções detalhadas**: Consulte `powerbi/README.md`

---

## Troubleshooting Power BI

**Erro de autenticação ao conectar:**
- Verifique se você tem permissões no SQL Database
- Use **Microsoft account** (não SQL Server authentication)
- Seu usuário Azure AD deve ter role `db_datareader` no database

**Dados não aparecem após refresh:**
- Verifique se as Azure Functions coletaram dados
- Execute queries SQL para confirmar dados no database
- Veja o histórico de refresh: Dataset → Settings → Refresh history

**Performance lento:**
- Limite o range de datas nos slicers
- Considere usar DirectQuery ao invés de Import
- Remova colunas não utilizadas das tabelas

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

## Estimativa de Custo

| Recurso | Custo Estimado |
|---------|----------------|
| Function App (Consumption) | ~$0.50/mês (3 functions × intervalo de 5min) |
| SQL Database (Serverless) | ~$5-10/mês |
| Application Insights | ~$0-2/mês (5GB free tier) |
| **Total** | **~$5-13/mês** |

---

## Recursos Adicionais

- **Código fonte**: `function_app/function_app.py`
- **SQL schemas**: `function_app/sql/`
- **Issue template**: `function_app/github_templates/incident.yml`
- **DORA Research**: https://dora.dev/
- **GitHub Actions**: https://docs.github.com/en/actions
- **Azure Functions**: https://learn.microsoft.com/azure/azure-functions/

---