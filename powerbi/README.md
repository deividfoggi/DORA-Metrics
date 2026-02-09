# DORA Metrics Power BI Template

Este diretório contém o template Power BI pré-configurado para visualização das DORA Metrics.

## 📁 Arquivos

- **`DORA-Metrics-Template.pbix`** - Template Power BI completo com modelo de dados, medidas DAX e visualizações

## 🚀 Início Rápido

### Pré-requisitos

1. **Power BI Desktop** instalado ([Download aqui](https://powerbi.microsoft.com/desktop/))
2. **Azure SQL Database** configurado com dados coletados
3. **Permissões** de leitura no SQL Database (role `db_datareader`)

### Passos para Usar o Template

#### 1. Abrir o Template

```bash
# Opção 1: Clique duas vezes no arquivo
DORA-Metrics-Template.pbix

# Opção 2: Abra via Power BI Desktop
File → Open → Selecione DORA-Metrics-Template.pbix
```

#### 2. Atualizar Conexão do Database

1. **Home** → **Transform data** → **Data source settings**

2. Clique na conexão do Azure SQL Database

3. Clique **Change Source...**

4. Atualize os valores:
   ```
   Server: seu-sql-server.database.windows.net
   Database: seu-database-name
   ```

5. Clique **OK**

#### 3. Atualizar Credenciais

1. Na mesma janela, clique **Edit Permissions...**

2. Em **Credentials**, clique **Edit...**

3. Selecione **Microsoft account**

4. Clique **Sign in** e autentique com sua conta Azure

5. Clique **Save** → **OK**

#### 4. Carregar os Dados

1. Se aparecer aviso amarelo no topo: **Refresh now**

2. Ou manualmente: **Home** → **Refresh**

3. Aguarde o carregamento (30-60 segundos)

#### 5. Verificar e Publicar

1. Navegue pelas 4 páginas do dashboard

2. Teste os slicers (Date Range, Repository, Environment)

3. **File** → **Publish** → **Publish to Power BI**

4. Selecione seu workspace

5. Configure refresh automático (próxima seção)

---

## 📊 O Que Está Incluído no Template

### Modelo de Dados

#### Tabelas Importadas:
- **`deployments`** - Deployments do GitHub Actions
- **`pull_requests`** - PRs mergeados
- **`incidents`** - GitHub Issues marcadas como incidents
- **`repositories`** - Metadados dos repositórios

#### Tabelas Calculadas:
- **`DeploymentIncidents`** - Relacionamento entre deployments e incidents (janela 24h)

#### Relacionamentos:
- `pull_requests[merge_commit_sha]` → `deployments[commit_sha]` (Many-to-One)

#### Colunas Calculadas:
- `deployments[Lead Time (Hours)]` - Tempo entre PR creation e deployment

### Medidas DAX (28 medidas)

#### Deployment Frequency:
- `Total Deployments`
- `Total Incidents`
- `Deployments Per Day`
- `Deployments MoM Change %`

#### Lead Time for Changes:
- `Median Lead Time (Hours)`
- `Average Lead Time (Hours)`
- `DORA Performance` (Elite/High/Medium/Low)

#### Change Failure Rate:
- `CFR %`
- `CFR Category`
- `CFR Color`
- `Deployments With Incidents`

#### Time to Restore Service:
- `Traditional MTTR - Mean (Hours)`
- `Traditional MTTR - Median (Hours)`
- `Deployment MTTR - Mean (Hours)`
- `Deployment MTTR - Median (Hours)`
- `Detection Lag - Median (Hours)`
- `DORA Tier - Traditional MTTR`
- `Closed Incidents Count`
- `Deployments with Closed Incidents`

### Páginas do Dashboard

#### Página 1: Deployment Frequency
- Cards: Total Deployments, Total Incidents
- Line Chart: Deployments Over Time por environment
- Bar Charts: Deployments por Repositório e Environment
- Slicers: Date Range, Repository, Environment

#### Página 2: Lead Time for Changes
- Cards: Median/Average Lead Time, DORA Performance
- Line Chart: Lead Time Trend
- Scatter Plot: Lead Time Distribution
- Table: Top 10 Longest Lead Times

#### Página 3: Change Failure Rate
- Cards: CFR %, Category, Deployment counts
- Combo Chart: CFR Trend + Deployment Volume
- Bar Chart: CFR by Repository
- Table: Recent Incidents with Deployments

#### Página 4: Time to Restore Service
- Cards: Traditional MTTR, Deployment MTTR, Detection Lag
- Line Chart: MTTR Trends Comparison
- Bar Chart: MTTR by Product
- Table: Incident Details with Resolution Times

### Tema e Formatação

- **Color Palette**: DORA-friendly (Green/Blue/Orange/Red)
- **Conditional Formatting**: Aplicado baseado nos tiers DORA
- **Slicers Sincronizados**: Date, Repository e Environment em todas as páginas
- **Interações**: Configuradas entre visuais

---

## ⚙️ Configuração Pós-Publicação

### Configure Refresh Automático

Após publicar no Power BI Service:

1. Navegue até o **Dataset** (não o Report)

2. Clique **⋯** → **Settings**

3. **Data source credentials**:
   - Clique **Edit credentials**
   - Selecione **OAuth2**
   - Autentique

4. **Scheduled refresh**:
   - **Keep your data up to date**: On
   - **Refresh frequency**: Daily
   - **Time zones**: Your timezone
   - **Time**: Adicione múltiplos horários
     ```
     6:00 AM
     2:00 PM
     10:00 PM
     ```
   - **Send refresh failure notifications to**: seu-email@company.com

5. **Apply**

### Configure Alertas

1. No dashboard, clique em qualquer **Card**

2. **⋯** → **Manage alerts**

3. **+ Add alert rule**

4. Exemplos de alertas recomendados:

   **CFR muito alto:**
   ```
   Condition: Above
   Threshold: 15
   Frequency: At most once per day
   ```

   **Lead Time alto:**
   ```
   Condition: Above
   Threshold: 168 (1 semana em horas)
   Frequency: At most once per day
   ```

   **MTTR alto:**
   ```
   Condition: Above
   Threshold: 24
   Frequency: At most once per day
   ```

### Compartilhar o Dashboard

**Opção 1: Compartilhar com usuários específicos**
1. No Report, clique **Share** (⤴️)
2. Adicione emails
3. Configure permissões:
   - ☑ Allow recipients to share
   - ☑ Allow recipients to build content (opcional)
4. **Grant access**

**Opção 2: Publicar na web (público)**
1. **File** → **Embed** → **Publish to web**
2. Copie o link embed
3. ⚠️ **Cuidado**: Dados ficam públicos na internet

**Opção 3: Adicionar ao workspace do Teams**
1. No Teams, vá para o canal
2. **+** → **Power BI**
3. Selecione o report

---

## 🎨 Personalização

### Modificar Visuais

#### Adicionar novo visual:
1. **Insert** → Escolha o tipo (Card, Chart, Table, etc.)
2. Arraste campos do painel **Data**
3. Configure em **Visualizations** e **Format**

#### Editar visual existente:
1. Clique no visual
2. Use **Visualizations** para mudar tipo
3. Use **Format** para estilo, cores, labels

#### Remover visual:
1. Selecione o visual
2. Pressione **Delete**

### Modificar Medidas DAX

#### Editar medida existente:
1. No painel **Data**, expanda `_Measures`
2. Clique na medida
3. Edite na barra de fórmulas no topo
4. Pressione **Enter**

#### Criar nova medida:
1. Clique com direito em `_Measures`
2. **New measure**
3. Digite a fórmula DAX:
   ```dax
   Minha Medida = 
   COUNTROWS(deployments)
   ```

#### Exemplos de medidas úteis:

**Deployments por semana:**
```dax
Deployments Per Week = 
DIVIDE(
    [Total Deployments],
    DATEDIFF(MIN(deployments[created_at]), MAX(deployments[created_at]), DAY) / 7,
    0
)
```

**Taxa de sucesso:**
```dax
Success Rate % = 
DIVIDE(
    CALCULATE(COUNTROWS(deployments), deployments[status] = "SUCCESS"),
    [Total Deployments],
    0
) * 100
```

**PR sem deployment:**
```dax
Undeployed PRs = 
COUNTROWS(
    FILTER(
        pull_requests,
        ISBLANK(
            RELATED(deployments[id])
        )
    )
)
```

### Adicionar Página Nova

1. Clique **+** no rodapé

2. Nomeie a página (clique direito na aba)

3. Adicione visuais

4. Configure slicers sincronizados:
   - **View** → **Sync slicers**
   - Marque as páginas para sincronizar

### Mudar Tema/Cores

#### Aplicar tema pronto:
1. **View** → **Themes**
2. Escolha um tema da galeria

#### Tema personalizado (JSON):
1. Crie arquivo `custom-theme.json`:
   ```json
   {
     "name": "DORA Custom",
     "dataColors": [
       "#10B981", "#3B82F6", "#F59E0B", "#EF4444"
     ],
     "background": "#FFFFFF",
     "foreground": "#1F2937",
     "good": "#10B981",
     "neutral": "#F59E0B",
     "bad": "#EF4444"
   }
   ```
2. **View** → **Themes** → **Browse for themes**
3. Selecione o arquivo JSON

#### Cores específicas de um visual:
1. Selecione o visual
2. **Format** → **Data colors**
3. Escolha cores manualmente ou por regra

---

## 🔧 Troubleshooting

### Erro: "Can't connect to the data source"

**Causa**: Credenciais inválidas ou expiradas

**Solução**:
1. **Home** → **Transform data** → **Data source settings**
2. Selecione a conexão
3. **Edit Permissions** → **Credentials** → **Edit**
4. Re-autentique com **Microsoft account**

### Erro: "Couldn't refresh the data"

**Causa**: Servidor SQL inacessível ou permissões insuficientes

**Solução**:
1. Verifique se o SQL Server está acessível:
   ```bash
   az sql db show \
     --resource-group $RESOURCE_GROUP \
     --server $SQL_SERVER_NAME \
     --name $SQL_DATABASE
   ```

2. Verifique permissões:
   ```sql
   SELECT 
       dp.name as user_name,
       r.name as role_name
   FROM sys.database_principals dp
   LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
   LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
   WHERE dp.name = 'seu-usuario@company.com';
   ```

3. Se necessário, adicione permissões:
   ```sql
   CREATE USER [seu-usuario@company.com] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [seu-usuario@company.com];
   ```

### Visuais Aparecem Vazios

**Causa**: Tabelas não têm dados ou filtros muito restritivos

**Solução**:
1. Verifique se há dados no SQL:
   ```sql
   SELECT COUNT(*) FROM deployments;
   SELECT COUNT(*) FROM pull_requests;
   SELECT COUNT(*) FROM incidents;
   ```

2. Limpe filtros:
   - **View** → **Filters**
   - Remova filtros em **Filters on all pages**

3. Amplie o range de datas no slicer

### Medidas Retornam BLANK ou Erro

**Causa**: Relacionamentos incorretos ou dados ausentes

**Solução**:
1. Verifique relacionamentos:
   - **Model View** (ícone de tabelas à esquerda)
   - Confirme que a linha liga as colunas certas

2. Adicione tratamento de erro na medida:
   ```dax
   Medida Segura = 
   IF(
       ISBLANK([Medida Original]),
       0,
       [Medida Original]
   )
   ```

3. Use DAX Debugger:
   - Clique na medida
   - Veja o resultado no **Data** pane

### Performance Lento

**Causas comuns**:
- Muitos dados (anos de histórico)
- Muitas medidas complexas
- Relacionamentos bidirecionais

**Soluções**:
1. **Limite o histórico**:
   ```dax
   -- Adicione filtro na importação
   -- Tabela deployments → Edit Query
   WHERE created_at >= DATEADD(year, -2, GETDATE())
   ```

2. **Remova relacionamentos bidirecionais** se não necessários

3. **Use agregações**:
   - Crie tabela resumida mensal
   - Use para visuais de tendência

4. **DirectQuery** ao invés de Import:
   - **Home** → **Transform data** → **Data source settings**
   - Change connection mode to **DirectQuery**
   - ⚠️ Mais lento em queries, mas dados sempre atualizados

---

## 📚 Recursos Adicionais

### Aprender Power BI:
- [Documentação Oficial](https://learn.microsoft.com/power-bi/)
- [DAX Guide](https://dax.guide/)
- [Power BI Community](https://community.powerbi.com/)

### DORA Metrics:
- [DORA Research](https://dora.dev/)
- [State of DevOps Report](https://cloud.google.com/devops/state-of-devops)

### Azure SQL:
- [Azure SQL Documentation](https://learn.microsoft.com/azure/azure-sql/)
- [Connection Troubleshooting](https://learn.microsoft.com/azure/azure-sql/database/troubleshoot-common-errors-issues)

---

## 🤝 Contribuindo

Se você fez melhorias no dashboard:

1. **Salve uma cópia**:
   - **File** → **Save As** → `DORA-Metrics-Template-v2.pbix`

2. **Documente mudanças**:
   - Atualize este README com novas medidas/visuais
   - Adicione screenshots se útil

3. **Compartilhe**: Substitua o template original se aprovado

---

## 📝 Notas Importantes

### Segurança:
- ⚠️ **NÃO** compartilhe o arquivo `.pbix` com credenciais embedadas
- Use sempre **Microsoft account** (OAuth2) para conexão
- Revise permissões antes de compartilhar dashboards

### Manutenção:
- Atualize o refresh schedule conforme necessidade
- Monitore alertas de falha de refresh
- Revise performance mensal (Query Performance Analyzer)

### Backup:
- Faça backup do `.pbix` antes de mudanças grandes
- Power BI Service mantém versões automáticas (limitado)

---

## ❓ Suporte

Para dúvidas ou problemas:

1. Consulte a seção **Troubleshooting** acima
2. Veja logs de refresh no Power BI Service (Dataset → Settings → Refresh history)
3. Revise a documentação oficial do Power BI
4. Abra uma issue no repositório principal

---

**Última atualização**: Fevereiro 2026  
**Versão do template**: 1.0  
**Compatível com**: Power BI Desktop (versão atual)
