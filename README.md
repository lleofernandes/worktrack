# ⏱️ Work Track

Aplicação de controle de horas, faturamento e análise financeira.

## Stack
- **Frontend/Backend MVP:** Streamlit
- **ORM:** SQLAlchemy 2.0
- **Banco padrão:** SQLite → preparado para PostgreSQL / SQL Server / MySQL

## Instalação

```bash
pip install -r requirements.txt
```

## Executar

```bash
streamlit run app.py
```

## Trocar banco de dados

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/worktrack"
streamlit run app.py
```

## Estrutura

```
worktrack/
├── app.py
├── config.py
├── requirements.txt
├── database/
│   ├── connection.py
│   ├── models.py
│   └── repository.py
├── services/
│   ├── worklog_service.py
│   ├── invoice_service.py
│   └── analytics_service.py
├── ui/
│   ├── worklog_form.py
│   ├── invoice_form.py
│   └── dashboard.py
└── utils/
    ├── date_utils.py
    └── calculations.py
```

## Roadmap

| Etapa | Status | Descrição |
|-------|--------|-----------|
| 1 | ✅ | Models SQLAlchemy + conexão |
| 2 | ⏳ | Form de controle de horas |
| 3 | ⏳ | Form de notas fiscais |
| 4 | ⏳ | Regras de cálculo (services) |
| 5 | ⏳ | Dashboard analítico |
| 6 | ⏳ | Repository pattern completo |
| 7 | ⏳ | Migração para PostgreSQL (Alembic) |
