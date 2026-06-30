from __future__ import annotations

from typing import Any

import streamlit as st

from db import get_supabase_client
from utils.validators import format_cnpj, is_valid_cnpj, only_digits


def _build_endereco_payload(
    cep: str,
    rua: str,
    numero: str,
    bairro: str,
    cidade: str,
    estado: str,
) -> dict[str, str]:
    """Monta o payload de endereco para armazenar em coluna JSONB."""
    return {
        "cep": only_digits(cep),
        "rua": rua.strip(),
        "numero": numero.strip(),
        "bairro": bairro.strip(),
        "cidade": cidade.strip(),
        "estado": estado.strip().upper(),
    }


def _build_socios_payload(quantidade: int, nonce: int) -> list[dict[str, str]]:
    """Le socios dinamicos do form e estrutura para coluna JSONB."""
    socios: list[dict[str, str]] = []
    for idx in range(quantidade):
        nome = st.session_state.get(f"socio_nome_{nonce}_{idx}", "").strip()
        cpf = only_digits(st.session_state.get(f"socio_cpf_{nonce}_{idx}", ""))
        participacao = st.session_state.get(f"socio_part_{nonce}_{idx}", "").strip()

        if nome:
            socios.append(
                {
                    "nome": nome,
                    "cpf": cpf,
                    "participacao": participacao,
                }
            )
    return socios


def _save_cliente(payload: dict[str, Any]) -> tuple[bool, str]:
    """Persiste cadastro na tabela clientes com tratamento de erros comuns."""
    try:
        client = get_supabase_client()
        response = client.table("clientes").insert(payload).execute()
        if getattr(response, "data", None) is None:
            return False, "Nao foi possivel confirmar a gravacao do cliente."
        return True, "Cliente cadastrado com sucesso."
    except Exception as exc:
        message = str(exc)
        normalized = message.lower()

        if "duplicate" in normalized or "23505" in normalized or "cnpj" in normalized:
            return False, "Ja existe cliente com este CNPJ cadastrado."
        if "connection" in normalized or "timeout" in normalized:
            return False, "Falha de conexao com o Supabase. Tente novamente."
        return False, f"Erro ao salvar cliente: {message}"


def render_cadastro_clientes() -> None:
    """Renderiza formulario robusto de cadastro de clientes."""
    st.title("Gestao de Clientes")
    st.caption("Cadastro completo com validacao fiscal e persistencia no Supabase.")

    if "clientes_form_nonce" not in st.session_state:
        st.session_state["clientes_form_nonce"] = 1

    nonce = st.session_state["clientes_form_nonce"]

    with st.form(key=f"cadastro_clientes_form_{nonce}", clear_on_submit=True):
        st.subheader("Dados principais")
        razao_social = st.text_input("Razao Social *", max_chars=180)
        cnpj_input = st.text_input("CNPJ *", placeholder="00.000.000/0000-00")
        cnpj_masked = format_cnpj(cnpj_input)
        st.caption(f"CNPJ formatado: {cnpj_masked or '-'}")

        st.subheader("Endereco")
        e1, e2, e3 = st.columns([1, 2, 1])
        with e1:
            cep = st.text_input("CEP *", placeholder="00000-000")
        with e2:
            rua = st.text_input("Rua *")
        with e3:
            numero = st.text_input("Numero *")

        e4, e5, e6 = st.columns([2, 2, 1])
        with e4:
            bairro = st.text_input("Bairro *")
        with e5:
            cidade = st.text_input("Cidade *")
        with e6:
            estado = st.text_input("Estado *", placeholder="UF", max_chars=2)

        st.subheader("Dados fiscais")
        regime_tributario = st.selectbox(
            "Regime Tributario *",
            ["Simples Nacional", "Presumido", "Real"],
            index=0,
        )

        st.subheader("Socios")
        qtd_socios = st.number_input(
            "Quantidade de socios",
            min_value=0,
            max_value=10,
            value=1,
            step=1,
        )

        for idx in range(int(qtd_socios)):
            s1, s2, s3 = st.columns([2, 1, 1])
            with s1:
                st.text_input(f"Nome do socio {idx + 1}", key=f"socio_nome_{nonce}_{idx}")
            with s2:
                st.text_input(
                    f"CPF do socio {idx + 1}",
                    key=f"socio_cpf_{nonce}_{idx}",
                    placeholder="000.000.000-00",
                )
            with s3:
                st.text_input(
                    f"Participacao (%) socio {idx + 1}",
                    key=f"socio_part_{nonce}_{idx}",
                    placeholder="50",
                )

        observacoes = st.text_area("Observacoes", height=120)

        submitted = st.form_submit_button("Salvar cliente", type="primary")

    if not submitted:
        return

    cnpj_digits = only_digits(cnpj_masked)
    required_fields = [
        razao_social.strip(),
        cnpj_digits,
        only_digits(cep),
        rua.strip(),
        numero.strip(),
        bairro.strip(),
        cidade.strip(),
        estado.strip(),
    ]

    if any(not field for field in required_fields):
        st.error("Preencha todos os campos obrigatorios marcados com *.")
        return

    if not is_valid_cnpj(cnpj_digits):
        st.error("CNPJ invalido. Revise os digitos verificadores.")
        return

    if len(only_digits(cep)) != 8:
        st.error("CEP invalido. Informe 8 digitos.")
        return

    if len(estado.strip()) != 2:
        st.error("Estado invalido. Informe a UF com 2 letras.")
        return

    endereco = _build_endereco_payload(
        cep=cep,
        rua=rua,
        numero=numero,
        bairro=bairro,
        cidade=cidade,
        estado=estado,
    )
    socios = _build_socios_payload(quantidade=int(qtd_socios), nonce=nonce)

    payload: dict[str, Any] = {
        "razao_social": razao_social.strip(),
        "cnpj": cnpj_digits,
        "endereco": endereco,
        "regime_tributario": regime_tributario,
        "socios": socios,
        "observacoes": observacoes.strip(),
    }

    ok, message = _save_cliente(payload)
    if ok:
        st.success(message)
        st.session_state["clientes_form_nonce"] += 1
        st.rerun()
    else:
        st.error(message)
