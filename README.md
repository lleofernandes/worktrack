# Work Track

Sistema de controle de horas trabalhadas e faturamento para prestadores de serviço MEI/PJ. Permite registrar apontamentos diários por contrato, emitir alertas de Notas Fiscais pendentes e acompanhar métricas de produtividade e receita via dashboard analítico.

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Interface | [Streamlit](https://streamlit.io/) |
| ORM / Banco | SQLAlchemy + SQLite (`worktrack.db`) |
| Linguagem | Python 3.11+ |
| Visualização | Plotly (gráficos interativos) |
| Estilo | CSS customizado via `ui/styles.py` |

---

## Estrutura de Diretórios

```
worktrack/
├── app.py                        # Entry point — configuração da página e roteamento
├── config.py                     # Configurações globais
├── seed.py                       # Dados iniciais para desenvolvimento/teste
├── worktrack.db                  # Banco SQLite (ignorado no git)
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── config.toml               # Tema e configurações do Streamlit
│
├── components/                   # Componentes visuais reutilizáveis
│   ├── dash_barchart.py          # Gráficos de barras: horas por contrato e detalhe diário
│   └── dash_linechart.py         # Gráfico de linha: evolução mensal por contrato
│
├── database/
│   ├── __init__.py
│   ├── connection.py             # Criação da engine e SessionLocal
│   ├── models.py                 # Modelos ORM (tabelas)
│   └── repository.py             # Repository Pattern — queries encapsuladas por entidade
│
├── services/
│   ├── __init__.py
│   ├── analytics_service.py      # Cálculos analíticos: métricas mensais, evolução, receita diária
│   ├── invoice_service.py        # Regras de negócio de Notas Fiscais
│   └── worklog_service.py        # Regras de negócio de apontamentos
│
├── ui/
│   ├── __init__.py
│   ├── dashboard.py              # Tela principal — filtros, KPIs, alertas e gráficos
│   ├── company_form.py           # Cadastro de empresas e contratos
│   ├── invoice_form.py           # Lançamento e listagem de Notas Fiscais
│   ├── worklog_form.py           # Registro de apontamentos de horas
│   └── styles.py                 # Injeção de CSS global
│
└── utils/
    ├── __init__.py
    ├── calculations.py           # Funções puras de cálculo (horas, receita, produtividade)
    ├── date_utils.py             # Utilitários de data (dias úteis, feriados)
    └── toast_helper.py           # Notificações de NF pendente via st.toast
```

---

## Modelos de Dados

### `companies`
Cadastro de empresas clientes.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER PK | Identificador |
| `name` | TEXT | Razão social |
| `fantasy_name` | TEXT | Nome fantasia |
| `cnpj` | TEXT UNIQUE | CNPJ |
| `created_at` | DATETIME | Data de criação |

---

### `contracts`
Contratos vinculados a uma empresa. Uma empresa pode ter múltiplos contratos ao longo do tempo (ex: reajuste de valor gera novo contrato).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER PK | Identificador |
| `company_id` | FK → companies | Empresa contratante |
| `contract_number` | TEXT | Número do contrato (ex: CTO-0006) |
| `contract_type` | ENUM | `WORK_HOUR`, `PROJECT`, `PROJECT_HOURS` |
| `start_date` | DATE | Início da vigência |
| `end_date` | DATE NULL | Fim da vigência — `NULL` = ativo |
| `monthly_fee` | DECIMAL NULL | Mensalidade fixa (PROJECT_HOURS) |
| `contracted_hours` | DECIMAL NULL | Pacote de horas (PROJECT_HOURS) |
| `overage_rate` | DECIMAL NULL | Taxa por hora excedente (PROJECT_HOURS) |
| `description` | TEXT NULL | Observações |

**Regra de status:**
- `end_date IS NULL` ou `end_date >= hoje` → **Ativo**
- `end_date < hoje` → **Inativo**

---

### `contract_rates_history`
Histórico de valores hora por contrato. Permite rastrear reajustes sem perder a referência dos apontamentos antigos.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER PK | Identificador |
| `contract_id` | FK → contracts | Contrato |
| `hour_rate` | DECIMAL | Valor R$/hora vigente no período |
| `start_date` | DATE | Início do valor |
| `end_date` | DATE NULL | Fim do valor — `NULL` = vigente |

---

### `work_logs`
Apontamentos diários de horas trabalhadas.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER PK | Identificador |
| `contract_id` | FK → contracts | Contrato ao qual o apontamento pertence |
| `date` | DATE | Data do trabalho |
| `start_time` | TIME NULL | Horário de início |
| `end_time` | TIME NULL | Horário de término |
| `break_minutes` | INTEGER | Minutos de intervalo |
| `extra_partner_minutes` | INTEGER | Minutos extras pagos pelo parceiro |
| `total_hours` | DECIMAL NULL | Horas totais (preenchido manualmente ou calculado) |
| `description` | TEXT NULL | Descrição da atividade |

**Cálculo de horas:** se `total_hours` estiver preenchido, usa diretamente. Caso contrário, calcula:
```
total = (end_time - start_time) - break_minutes + extra_partner_minutes
```

---

### `invoices`
Notas Fiscais emitidas por contrato/mês.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER PK | Identificador |
| `contract_id` | FK → contracts | Contrato faturado |
| `issue_date` | DATE | Data de emissão da NF |
| `invoice_number` | TEXT | Número da NF |
| `amount` | DECIMAL | Valor em R$ |
| `origin` | TEXT NULL | Origem (ex: NF GOV BR) |
| `notes` | TEXT NULL | Observações (ex: "NF Cancelada") |
| `created_at` | DATETIME | Data de registro |

> **NF cancelada:** registros com `amount = 0` são considerados cancelados e ignorados no alerta de pendências.

---

### `holidays`
Feriados nacionais e opcionais, usados no cálculo de dias úteis.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER PK | Identificador |
| `date` | DATE UNIQUE | Data do feriado |
| `description` | TEXT | Nome do feriado |
| `is_national` | BOOL | Feriado nacional |
| `is_optional` | BOOL | Feriado opcional/ponto facultativo |
| `observation` | TEXT NULL | Observações |

---

## Tipos de Contrato

| Tipo | Descrição | Cálculo de Receita |
|------|-----------|-------------------|
| `WORK_HOUR` | Faturamento por hora trabalhada | `horas_trabalhadas × taxa_hora` (via `contract_rates_history`) |
| `PROJECT` | Projeto fechado com valor fixo negociado | Sem cálculo automático — controlado via NF |
| `PROJECT_HOURS` | Pacote de horas mensais com mensalidade | `monthly_fee` + excedente se `horas > contracted_hours` |

---

## Regras de Negócio

### Horas Esperadas

| Tipo de contrato | Fórmula |
|-----------------|---------|
| `WORK_HOUR` / `PROJECT` | `dias_úteis_do_mês × 8h` |
| `PROJECT_HOURS` | `contracted_hours` do contrato (pacote fixo) |

### Dias Úteis
Calculados como dias de segunda a sexta que **não são feriados** cadastrados na tabela `holidays`.

Quando o dashboard exibe múltiplos contratos no mesmo período, os dias úteis são **deduplicados por `(ano, mês)`** para evitar contagem duplicada:

```python
seen_periods: dict[tuple, int] = {}
for m in metrics_list:
    key = (m.year, m.month)
    seen_periods[key] = m.business_days   # sobrescreve — mesmo valor para todos os contratos do mês
biz_days = sum(seen_periods.values())
```

### Produtividade

```
produtividade (%) = (horas_trabalhadas / horas_esperadas) × 100
```

- ≥ 100% → meta atingida (🟢)
- < 100% → abaixo da meta (🔴)

### Receita Realizada — `PROJECT_HOURS`

```
se horas_trabalhadas ≤ contracted_hours:
    receita = monthly_fee
senão:
    receita = monthly_fee + (horas_excedentes × overage_rate)
```

### Alerta de NF Pendente

Para cada contrato e ano verificado, o sistema compara:
- Meses com `work_logs` registrados (`WorkLogRepository.get_months_with_logs`)
- Meses com `invoices` emitidas com `amount > 0` (`InvoiceRepository.get_months_with_invoices`)

Meses com apontamentos **sem NF correspondente** são sinalizados como pendentes.
O mês corrente é classificado como "Em andamento" (normal — NF ainda não emitida).

**Escopo:** o alerta respeita o filtro de status da tela (Ativo/Inativo/Todos) e itera apenas sobre os contratos já filtrados — não cruza dados entre contratos de mesma empresa.

---

## Dashboard — Filtros e Comportamento

| Filtro | Padrão | Efeito |
|--------|--------|--------|
| Status Contrato | Ativo | Filtra contratos por `end_date` |
| Mês | Mês atual | Define período dos KPIs |
| Ano | Ano atual | Define período dos KPIs e alertas |
| Contrato | Todos | Permite detalhar um contrato específico |

### KPIs exibidos

**Bloco Horas:**
- Dias Úteis (deduplicados por `(ano, mês)`)
- Dias Trabalhados
- Horas Esperadas
- Horas Trabalhadas (com delta)

**Bloco Receita & Produtividade:**
- Receita Esperada
- Receita Realizada (com delta)
- Produtividade (%) com barra de progresso

### Gráficos

| Gráfico | Localização | Dados |
|---------|-------------|-------|
| Horas por Contrato | Col. esquerda | Barras: horas ou receita por empresa (tabs) |
| Evolução por Mês/Ano | Col. direita | Linha: horas, receita e produtividade mensais — ordenação cronológica via Plotly |
| Detalhe Diário | Abaixo | Barras: horas e receita por dia — exibido apenas quando contrato + mês + ano estão selecionados |

---

## Boas Práticas Operacionais

1. **Crie o contrato antes de registrar apontamentos.** Ao haver reajuste de valor ou renovação, cadastre o novo contrato com a nova `start_date` **antes** de registrar os work logs do novo período. Isso garante que os apontamentos fiquem vinculados ao `contract_id` correto desde o início.

2. **NF cancelada.** Mantenha o registro com `amount = 0` e `notes = "NF Cancelada"`. O sistema ignora automaticamente NFs com `amount = 0` no alerta de pendências.

3. **Histórico de taxas.** Nunca altere uma taxa existente em `contract_rates_history`. Sempre encerre a taxa atual (`end_date = data_do_reajuste - 1 dia`) e crie uma nova entrada com o novo valor e `start_date`.

4. **Feriados.** Cadastre os feriados do ano antes de iniciar os lançamentos para garantir o cálculo correto de dias úteis e horas esperadas.

5. **Múltiplos contratos por empresa.** Quando uma empresa renova o contrato com novo valor/hora, o contrato anterior deve ter `end_date` preenchido. O alerta de NF considera **cada contrato individualmente** — os apontamentos de 2024 devem estar no contrato de 2024, não no contrato de 2025.

---

## Instalação e Execução

```bash
# 1. Clone o repositório
git clone <repo-url>
cd worktrack

# 2. Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
.venv\Scripts\activate          # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Execute a aplicação
streamlit run app.py
```

O banco `worktrack.db` é criado automaticamente na primeira execução via `init_db()` em `database/connection.py`.

---

## Navegação da Aplicação

| Tela | Descrição |
|------|-----------|
| 📊 Dashboard | KPIs, alertas de NF, gráficos de evolução e detalhe diário |
| ⏱️ Controle de Horas | Registro e listagem de apontamentos por contrato |
| 🧾 Notas Fiscais | Lançamento e histórico de NFs por contrato |
| 🗂️ Cadastros | Gerenciamento de empresas, contratos e taxas |

---

## Configuração

Configurações centralizadas em `config.py`. O arquivo `.streamlit/config.toml` controla tema, layout e porta padrão da aplicação.

Arquivos ignorados pelo git (`.gitignore`):

```
worktrack.db       # banco de dados local
*.sqlite3 / *.db   # outros bancos
.env               # variáveis de ambiente sensíveis
files_project/     # arquivos locais de projeto
.venv/             # ambiente virtual
__pycache__/       # artefatos Python
```
