# 📁 Salve seu arquivo Power BI aqui

## Instruções

Após criar seu dashboard Power BI completo seguindo todos os passos:

1. **Salve o arquivo neste diretório**:
   ```
   powerbi/
     ├── DORA-Metrics-Template.pbix  ← Salve aqui
     ├── README.md
     └── PLACE_PBIX_FILE_HERE.md (este arquivo)
   ```

2. **Nome do arquivo**: `DORA-Metrics-Template.pbix`

3. **Como salvar**:
   - No Power BI Desktop: **File** → **Save As**
   - Navegue até este diretório
   - Nome: `DORA-Metrics-Template.pbix`
   - Clique **Save**

## ⚠️ Importante

Antes de salvar, certifique-se que:

- ☑ Todas as 4 páginas do dashboard estão criadas
- ☑ Todas as medidas DAX estão funcionando
- ☑ Tema está aplicado
- ☑ Slicers estão sincronizados
- ☑ **NÃO há credenciais embedadas** (use Microsoft Account com OAuth2)

## 🔒 Segurança

**NUNCA** salve credenciais no arquivo `.pbix`:
- Use sempre **Microsoft account** (OAuth2) para conexão SQL
- Não use SQL Server Authentication com senha
- Revise **Home** → **Transform data** → **Data source settings** antes de salvar

## 📤 Compartilhando

Após salvar aqui, outros usuários podem:

1. Abrir o arquivo `DORA-Metrics-Template.pbix`
2. Atualizar a conexão para seu SQL Database
3. Autenticar com suas próprias credenciais
4. Refresh e usar imediatamente

**Economia de tempo**: ~2 horas → ~10 minutos! 🚀

---

## Próximos Passos

Após salvar o `.pbix` aqui:

1. Teste abrindo novamente para confirmar que funciona
2. Delete este arquivo (`PLACE_PBIX_FILE_HERE.md`)
3. Commit para o repositório Git
4. Compartilhe com a equipe

```bash
# Exemplo de commit
git add powerbi/DORA-Metrics-Template.pbix
git commit -m "Add Power BI template for DORA metrics"
git push
```
