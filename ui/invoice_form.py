"""
invoice_form.py — UI Streamlit para controle de Notas Fiscais.
Sem regras de negócio aqui — tudo delegado ao invoice_service.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from database.connection import SessionLocal
from services.invoice_service import (
    InvoiceValidationError,
    create_invoice,
    delete_invoice,
    get_all_companies,
    list_invoices,
)


def render_invoice_form() -> None:
    st.header("🧾 Notas Fiscais")

    tab_new, tab_history = st.tabs(["➕ Nova NF", "📋 Histórico"])

    with tab_new:
        _render_new_form()

    with tab_history:
        _render_history()


# ---------------------------------------------------------------------------
# Formulário de nova NF
# ---------------------------------------------------------------------------

def _render_new_form() -> None:
    session = SessionLocal()
    try:
        companies = get_all_companies(session)

        if not companies:
            st.warning("Nenhuma empresa cadastrada. Cadastre uma empresa antes de emitir NFs.")
            return

        # ── Linha 1: Data + Empresa ──────────────────────────────────────
        col1, col2 = st.columns([1, 2])

        with col1:
            issue_date = st.date_input(
                "Data de Emissão *",
                value=date.today(),
                format="DD/MM/YYYY",
            )

        with col2:
            company_options = {c.name: c for c in companies}
            company_name = st.selectbox(
                "Empresa (Tomador) *",
                options=list(company_options.keys()),
                key="inv_company",
            )
            company = company_options[company_name]

        # ── Auto-fill: dados da empresa ───────────────────────────────────
        with st.container(border=True):
            af1, af2, af3 = st.columns(3)
            af1.text_input("Razão Social", value=company.name, disabled=True)
            af2.text_input("Nome Fantasia", value=company.fantasy_name or "—", disabled=True)
            af3.text_input("CNPJ", value=company.cnpj or "—", disabled=True)

        # ── Linha 2: Número NF + Valor ────────────────────────────────────
        col3, col4 = st.columns(2)

        with col3:
            invoice_number = st.text_input(
                "Número da NF *",
                placeholder="Ex: 000123",
                key="inv_number",
            )

        with col4:
            amount = st.number_input(
                "Valor (R$) *",
                min_value=0.01,
                value=1.00,
                step=100.00,
                format="%.2f",
                key="inv_amount",
            )

        # ── Linha 3: Origem + Observações ─────────────────────────────────
        col5, col6 = st.columns([1, 2])

        with col5:
            origin = st.text_input(
                "Origem / Competência",
                placeholder="Ex: Abril/2026 — Consultoria BI",
                key="inv_origin",
            )

        with col6:
            notes = st.text_area(
                "Observações (máx. 255 caracteres)",
                placeholder="Informações adicionais sobre a NF...",
                height=80,
                max_chars=255,
                key="inv_notes",
            )
            if notes:
                st.caption(f"{len(notes)}/255 caracteres")

        # ── Submit ────────────────────────────────────────────────────────
        submitted = st.button("💾 Salvar NF", type="primary", use_container_width=True)

        if submitted:
            try:
                invoice = create_invoice(
                    session=session,
                    company_id=company.id,
                    issue_date=issue_date,
                    invoice_number=invoice_number,
                    amount=float(amount),
                    origin=origin,
                    notes=notes,
                )
                session.commit()
                st.success(
                    f"✅ NF #{invoice.invoice_number} salva! "
                    f"Empresa: {company.name} — Valor: R$ {float(invoice.amount):,.2f}"
                )
                st.rerun()
            except InvoiceValidationError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro ao salvar: {e}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Histórico de NFs
# ---------------------------------------------------------------------------

def _render_history() -> None:
    session = SessionLocal()
    try:
        companies = get_all_companies(session)

        # Filtros
        fc1, fc2, fc3 = st.columns(3)

        with fc1:
            filter_options = {"Todas": None}
            filter_options.update({c.name: c.id for c in companies})
            filter_company = st.selectbox(
                "Filtrar por empresa",
                options=list(filter_options.keys()),
                key="inv_hist_company",
            )

        with fc2:
            filter_month = st.selectbox(
                "Mês",
                options=list(range(1, 13)),
                index=date.today().month - 1,
                format_func=lambda m: date(2000, m, 1).strftime("%B").capitalize(),
                key="inv_hist_month",
            )

        with fc3:
            filter_year = st.selectbox(
                "Ano",
                options=list(range(date.today().year - 2, date.today().year + 1)),
                index=2,
                key="inv_hist_year",
            )

        invoices = list_invoices(
            session,
            company_id=filter_options[filter_company],
            month=filter_month,
            year=filter_year,
        )

        if not invoices:
            st.info("Nenhuma NF encontrada para os filtros selecionados.")
            return

        # Tabela
        rows = []
        for inv in invoices:
            rows.append({
                "ID": inv.id,
                "Data Emissão": inv.issue_date.strftime("%d/%m/%Y"),
                "Nº NF": inv.invoice_number,
                "Empresa": inv.company.name if inv.company else "—",
                "CNPJ": inv.company.cnpj if inv.company else "—",
                "Valor": f"R$ {float(inv.amount):,.2f}",
                "Origem": inv.origin or "—",
                "Observações": (inv.notes or "")[:50],
            })

        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Totais
        total_amount = sum(float(inv.amount) for inv in invoices)
        t1, t2 = st.columns(2)
        t1.metric("Total de NFs", len(invoices))
        t2.metric("Valor total faturado", f"R$ {total_amount:,.2f}")

        # Gráfico de barras por empresa (se houver mais de 1)
        company_totals = {}
        for inv in invoices:
            name = inv.company.name if inv.company else "—"
            company_totals[name] = company_totals.get(name, 0) + float(inv.amount)

        if len(company_totals) > 1:
            st.subheader("Faturamento por Empresa")
            import pandas as pd
            chart_df = pd.DataFrame(
                list(company_totals.items()), columns=["Empresa", "Valor (R$)"]
            ).sort_values("Valor (R$)", ascending=False)
            st.bar_chart(chart_df.set_index("Empresa"))

        # Delete
        with st.expander("🗑️ Remover NF"):
            del_id = st.number_input("ID da NF", min_value=1, step=1, key="inv_del_id")
            if st.button("Remover NF", type="secondary"):
                found = delete_invoice(session, int(del_id))
                if found:
                    session.commit()
                    st.success(f"NF #{del_id} removida.")
                    st.rerun()
                else:
                    st.error(f"NF #{del_id} não encontrada.")
    finally:
        session.close()
