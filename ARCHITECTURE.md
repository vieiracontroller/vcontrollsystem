# V-Controll System - Estrutura sugerida (Arquitetura Limpa)

## Objetivo
Organizar o projeto Streamlit + Supabase com separacao entre interface, regras de negocio e acesso a dados.

## Estrutura recomendada

```text
V-Controll System/
  app.py                      # Entrypoint Streamlit (menu + roteamento)
  fiscal.py                   # Modulo Fiscal (UI + orquestracao de importacao XML)
  db.py                       # Cliente Supabase centralizado
  requirements.txt            # Dependencias da aplicacao

  app/
    __init__.py
    pages/
      __init__.py
      dashboard.py            # Tela executiva (KPIs)
      contabil.py             # Tela do modulo contabil
      dp.py                   # Tela do modulo departamento pessoal

  database/
    # Reservado para repositorios e migracoes SQL

  utils/
    # Reservado para parsers, validacoes e helpers compartilhados
```

## Convencoes adotadas
- UI em Streamlit fica na camada app/pages e modulos de entrada.
- Integracao com banco fica centralizada em db.py.
- Processamento de XML no modulo fiscal e pronto para extrair utilitarios para utils/.
- Segredos de infraestrutura ficam em st.secrets.

## Motor de Download NF-e (Servico licensiavel)

### Componentes
- `fiscal/nfe_downloader.py`: orquestrador de servico sem dependencia de Streamlit.
- `fiscal/certificados.py`: carga e validacao de certificado A1 por cliente.
- `fiscal/receita_federal_gateway.py`: comunicacao HTTP mTLS com distribuicao DF-e.

### Fluxo Receita/SEFAZ
1. Resolver `cliente_id` por XML ou CNPJ informado.
2. Carregar A1 ativo em `certificados_clientes` e validar senha/validade.
3. Consultar `planos_contratados` para liberar download/apuracao/SPED.
4. Chamar gateway de distribuicao DF-e com mTLS (certificado + chave privada).
5. Descompactar `docZip` retornado pelo webservice em XML NF-e.
6. Persistir em `fiscal_nfe_imports`, sincronizar produtos e registrar `logs_de_uso`.

### Persistencia de apoio
- `planos_contratados`: controle de recursos por cliente.
- `logs_de_uso`: auditoria para billing SaaS.
- `certificados_clientes`: armazenamento do A1 (PFX base64 + senha).
- `nfe_distribuicao_cursor`: cursor de NSU para consultas incrementais.

### Configuracoes de ambiente
- `NFE_DFE_URL_PRODUCAO`
- `NFE_DFE_URL_HOMOLOGACAO`

## Segredos esperados (Streamlit Cloud)

```toml
[supabase]
url = "https://SEU-PROJETO.supabase.co"
key = "SUA_SERVICE_ROLE_OU_ANON_KEY"
```

Ou variaveis planas:

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_KEY = "SUA_SERVICE_ROLE_OU_ANON_KEY"
```
