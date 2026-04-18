"""
seed.py — Dados de exemplo para testes locais.
Execute: python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date
from decimal import Decimal
from database.connection import init_db, SessionLocal
from database.models import Company, ContractRateHistory, Project, Holiday, ContractType

def seed():
    init_db()
    session = SessionLocal()

    try:
        # Verifica se já existe seed
        if session.query(Company).count() > 0:
            print("Seed já aplicado. Nada a fazer.")
            return

        # Empresas
        imaps = Company(
            name="iMaps",
            fantasy_name="iMaps Analytics",
            cnpj="11.564.730/0001-31",
            contract_type=ContractType.WORK_HOUR,
            contract_number="CT-2024-001",
        )
        oleon = Company(
            name="Oleon Brasil",
            fantasy_name="Oleon Brasil Ltda",
            cnpj="61.278.875/0001-44",
            contract_type=ContractType.WORK_HOUR,
            contract_number="CT-2024-002",
        )
        session.add_all([imaps, oleon])
        session.flush()

        # Taxas horárias
        session.add_all([
            ContractRateHistory(
                company_id=imaps.id,
                hour_rate=Decimal("85.00"),
                start_date=date(2024, 1, 1),
                end_date=None,
            ),
            ContractRateHistory(
                company_id=oleon.id,
                hour_rate=Decimal("95.00"),
                start_date=date(2024, 1, 1),
                end_date=None,
            ),
        ])

        # Projetos
        session.add_all([
            Project(company_id=imaps.id,  name="HedgePoint - BI",        description="Power BI e Athena"),
            Project(company_id=imaps.id,  name="HedgePoint - Automação",  description="Power Automate"),
            Project(company_id=oleon.id,  name="Oleon - Relatórios SAP",  description="SQL SAP + Power BI"),
        ])

        # Feriados nacionais 2025/2026
        holidays = [
            (date(2026, 1, 1),  "Confraternização Universal",   True),
            (date(2026, 4, 21), "Tiradentes",                   True),
            (date(2026, 5, 1),  "Dia do Trabalho",              True),
            (date(2026, 9, 7),  "Independência do Brasil",      True),
            (date(2026, 10, 12),"Nossa Senhora Aparecida",      True),
            (date(2026, 11, 2), "Finados",                      True),
            (date(2026, 11, 15),"Proclamação da República",     True),
            (date(2026, 12, 25),"Natal",                        True),
        ]
        for d, desc, national in holidays:
            session.add(Holiday(date=d, description=desc, is_national=national))

        session.commit()
        print("✅ Seed aplicado com sucesso!")
        print(f"   Empresas: iMaps (R$ 85/h), Oleon Brasil (R$ 95/h)")
        print(f"   Projetos: 3 criados")
        print(f"   Feriados: {len(holidays)} cadastrados")

    except Exception as e:
        session.rollback()
        print(f"❌ Erro no seed: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
