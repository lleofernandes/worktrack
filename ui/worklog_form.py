"""
worklog_form.py — Formulário de controle de horas (por contrato).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

import streamlit as st

from database.connection import SessionLocal
from database.models import ContractType
from database.repository import (
    CompanyRepository, ContractRepository,
    ContractRateRepository, ProjectRepository, WorkLogRepository,
)
from utils.calculations import calc_worked_hours
from utils.toast_helper import set_toast, show_pending_toast

CONTRACT_LABELS = {
    "WORK_HOUR":     "Por Hora",
    "PROJECT":       "Projeto Fechado",
    "PROJECT_HOURS": "Projeto c/ Horas",
}


def render_worklog_form() -> None:
    st.header("⏱️ Controle de Horas")
    show_pending_toast()

    session = SessionLocal()
    try:
        tab_hist, tab_form  = st.tabs(["📋 Histórico", "➕ Adicionar"])        
        with tab_hist:
            _render_history(session)
            
        with tab_form:
            _render_form(session)
            
    finally:
        session.close()


def _render_form(session) -> None:
    # Busca contratos ativos de todas as empresas
    contracts = ContractRepository.get_all(session, active_only=True)
    if not contracts:
        st.warning("Nenhum contrato ativo cadastrado. Cadastre uma empresa e um contrato primeiro.")
        return

    contract_options = {
        f"[{ct.id}] {ct.company.name if ct.company else '?'} — {ct.contract_number or 'S/N'} ({CONTRACT_LABELS.get(ct.contract_type.value, ct.contract_type.value)})": ct.id
        for ct in contracts
    }

    col1, col2 = st.columns(2)
    with col1:
        selected_label = st.selectbox("Contrato *", list(contract_options.keys()), key="wl_contract")
        contract_id = contract_options[selected_label]
    with col2:
        log_date = st.date_input("Data *", value=date.today(), format="DD/MM/YYYY", key="wl_date")

    contract = ContractRepository.get_by_id(session, contract_id)
    rate_obj  = ContractRateRepository.get_active_rate(session, contract_id, log_date)
    contract_type = contract.contract_type if contract else ContractType.WORK_HOUR

    with st.container(border=True):
        ci1, ci2, ci3, ci4 = st.columns(4)
        # ci1.metric("Empresa", contract.company.name if contract and contract.company else "—")
        # ci2.metric("Tipo", CONTRACT_LABELS.get(contract_type.value, contract_type.value))
        # ci3.metric("Nº Contrato", contract.contract_number or "—")
        # ci4.metric("Taxa/h", f"R$ {float(rate_obj.hour_rate):,.2f}" if rate_obj else "⚠️ Sem taxa")
        
        def field(label, value):
                st.markdown(f"""
                    <div style="line-height:2.1">
                        <div style="font-size:14px; text-align: center; color:gray; padding: 0;">{label}</div>
                        <div style="font-size:18px; text-align: center; padding: 0 0 5px 0; ">{value}</div>
                    </div>
                """, unsafe_allow_html=True)
        
        with ci1:
            field("Empresa", contract.company.fantasy_name or "—")
            
        with ci2:
            field("Tipo de Contrato", CONTRACT_LABELS.get(contract_type.value, contract_type.value))
            
        with ci3:
            field("Nº Contrato", contract.contract_number or "—")
            
        with ci4:
            field("Taxa/h", f"R$ {float(rate_obj.hour_rate):,.2f}" if rate_obj else "⚠️ Sem taxa")

    projects = ProjectRepository.get_all_by_contract(session, contract_id)
    project_options = {"— Nenhum —": None}
    project_options.update({p.name: p.id for p in projects})
    selected_project = st.selectbox("Projeto (opcional)", list(project_options.keys()), key="wl_project")
    project_id = project_options[selected_project]

    st.divider()

    if contract_type == ContractType.WORK_HOUR:
        start_time, end_time, break_minutes, extra_hours, total_hours, progress_pct = _fields_work_hour()
    elif contract_type == ContractType.PROJECT_HOURS:
        start_time, end_time, break_minutes, extra_hours, total_hours, progress_pct = _fields_project_hours()
    else:
        start_time, end_time, break_minutes, extra_hours, total_hours, progress_pct = _fields_project()

    description = st.text_area("Descrição / Atividades", height=100, key="wl_desc",
                                placeholder="Descreva as atividades realizadas...")

    preview_hours = _preview_hours(contract_type, start_time, end_time, break_minutes, extra_hours, total_hours)
    if preview_hours and preview_hours > 0:
        rev = float(preview_hours) * float(rate_obj.hour_rate) if rate_obj else 0
        pc1, pc2 = st.columns(2)
        pc1.info(f"⏱️ **{float(preview_hours):.2f}h calculadas**")
        if rate_obj:
            pc2.info(f"💰 **R$ {rev:,.2f} estimado**")

    if st.button("💾 Salvar Apontamento", type="primary", use_container_width=True, key="wl_save"):
        error = _validate(contract_type, start_time, end_time, break_minutes, total_hours, progress_pct, preview_hours)
        if error:
            st.error(f"❌ {error}")
        else:
            try:
                wl = WorkLogRepository.create(
                    session,
                    contract_id=contract_id,
                    project_id=project_id,
                    date=log_date,
                    start_time=start_time,
                    end_time=end_time,
                    break_minutes=break_minutes or 0,
                    extra_partner_minutes=int(extra_hours or 0),
                    total_hours=Decimal(str(total_hours)) if total_hours is not None else None,
                    progress_pct=progress_pct,
                    description=description.strip() if description else None,
                )
                session.commit()
                label = f"{float(preview_hours):.2f}h" if preview_hours else "registro"
                set_toast(f"✅ Apontamento #{wl.id} salvo — {label} em {log_date.strftime('%d/%m/%Y')}!")
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro: {e}")


def _fields_work_hour():
    st.caption("⏰ **Por Hora** — informe o horário trabalhado")
    c1, c2, c3, c4 = st.columns(4)
    with c1: start_time = st.time_input("Início *", value=time(9, 0), step=1800, key="wl_start")
    with c2: end_time   = st.time_input("Término *", value=time(18, 0), step=1800, key="wl_end")
    with c3: break_min  = st.number_input("Intervalo (min)", 0, 480, 60, 15, key="wl_break")
    with c4: extra = st.number_input("Extra Parceiro (min)", min_value=0, max_value=480,  value=0, step=5, key="wl_extra", help="Minutos extras do parceiro. Ex: 45, 90, 120...")
    return start_time, end_time, break_min, extra, None, None


def _fields_project_hours():
    st.caption("📦 **Projeto c/ Horas** — total de horas do período")
    c1, c2 = st.columns([1, 2])
    with c1:
        total = st.number_input("Total de Horas *", 0.25, 24.0, 8.0, 0.25, format="%.2f", key="wl_total")
    with c2:
        h, m = int(total), int((total % 1) * 60)
        st.info(f"⏱️ **{h}h {m:02d}min** de trabalho no projeto.")
    return None, None, 0, 0.0, total, None


def _fields_project():
    st.caption("🎯 **Projeto Fechado** — registre o avanço")
    c1, c2 = st.columns([1, 2])
    with c1:
        pct = st.slider("% Avanço", 0, 100, 0, 5, key="wl_progress")
    with c2:
        if pct == 0:       st.warning("🔴 Não iniciado")
        elif pct < 50:     st.info(f"🔵 Em andamento: {pct}%")
        elif pct < 100:    st.success(f"🟢 Quase lá: {pct}%")
        else:              st.success("✅ 100% concluído!")
    st.caption("ℹ️ Faturamento controlado pela tela de Notas Fiscais.")
    return None, None, 0, 0.0, None, pct


def _preview_hours(ct, start, end, brk, extra, total):
    if ct == ContractType.WORK_HOUR and start and end and end > start:
        try: return calc_worked_hours(start, end, brk or 0, extra or 0)
        except: return None
    if ct == ContractType.PROJECT_HOURS and total:
        return Decimal(str(total))
    return None


def _validate(ct, start, end, brk, total, pct, preview):
    if ct == ContractType.WORK_HOUR:
        if not start or not end: return "Horário de início e término obrigatórios."
        if end <= start:          return "Término deve ser maior que início."
        if preview and preview > 24: return "Horas não podem exceder 24h/dia."
        if preview and preview <= 0: return "Total de horas deve ser maior que zero."
    elif ct == ContractType.PROJECT_HOURS:
        if not total or total <= 0: return "Informe o total de horas (> 0)."
        if total > 24:              return "Total não pode exceder 24h/dia."
    elif ct == ContractType.PROJECT:
        if pct is None:             return "Informe o percentual de avanço."
    return None


def _render_history(session) -> None:
    import pandas as pd

    companies = CompanyRepository.get_all(session)
    co_opts = {"Todas": None}
    co_opts.update({c.name: c.id for c in companies})

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sel = st.selectbox("Empresa", list(co_opts.keys()), key="hist_company")
        filter_company = co_opts[sel]
    with fc2:
        mo = {"Todos": None, **{date(2000, m, 1).strftime("%B").capitalize(): m for m in range(1, 13)}}
        ml = st.selectbox("Mês", list(mo.keys()),
                           index=list(mo.keys()).index(date(2000, date.today().month, 1).strftime("%B").capitalize()),
                           key="hist_month")
        filter_month = mo[ml]
    with fc3:
        filter_year = st.selectbox("Ano",
                                    list(range(date.today().year - 2, date.today().year + 1)),
                                    index=2, key="hist_year")

    logs = WorkLogRepository.list_filtered(
        session, company_id=filter_company, month=filter_month, year=filter_year
    )
    if not logs:
        st.info("Nenhum apontamento encontrado.")
        return

    rows = []
    total_receita = 0.0
    total_horas   = 0.0
    
    for wl in logs:
        ct = wl.contract.contract_type if wl.contract else ContractType.WORK_HOUR
        if ct == ContractType.WORK_HOUR and wl.start_time and wl.end_time:
            try: h = calc_worked_hours(wl.start_time, wl.end_time, wl.break_minutes, float(wl.extra_partner_hours))
            except: h = Decimal("0")
            info = f"{wl.start_time.strftime('%H:%M')} → {wl.end_time.strftime('%H:%M')}"
        elif ct == ContractType.PROJECT_HOURS and wl.total_hours:
            h, info = wl.total_hours, f"{float(wl.total_hours):.2f}h (total)"
        else:
            h, info = Decimal("0"), f"Avanço: {wl.progress_pct or 0}%"

        rate_obj = ContractRateRepository.get_active_rate(session, wl.contract_id, wl.date)
        rev = float(h) * float(rate_obj.hour_rate) if rate_obj and h > 0 else 0
        empresa = wl.contract.company.name if wl.contract and wl.contract.company else "—"

        rows.append({
            "Data": wl.date.strftime("%d/%m/%Y"),
            "Empresa": empresa,
            "Tipo": CONTRACT_LABELS.get(ct.value, ct.value),
            "Info": info,
            "Horas": f"{float(h):.2f}h" if h > 0 else "—",
            "Receita": f"R$ {rev:,.2f}" if rev > 0 else "—",
            "Descrição": (wl.description or "")[:60],
        })

        total_horas   += float(h) if h else 0
        total_receita += rev
        
        # ── Big numbers no canto superior direito ──────────────────────────
    c1, c2 = st.columns([2, 1])
    with c2:
        st.markdown(
            f"""
            <div style="text-align:right; padding-bottom: 4px;">                
                <div style="font-size:16px; color:#888; font-weight:400;">Total do período: R$ {total_receita:,.2f}</div>
                <div style="font-size:14px; color:#888; margin-top:2px;">Horas trabalhadas: {total_horas:.2f}h </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"{len(logs)} apontamento(s).")
