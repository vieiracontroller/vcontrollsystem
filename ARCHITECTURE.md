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
