import streamlit as st

from app.pages.contabil import render_contabil_module
from app.pages.dashboard import render_dashboard
from app.pages.dp import render_dp_module
from fiscal import render_fiscal_module


def main() -> None:
	"""Ponto de entrada da UI com navegacao lateral entre modulos."""
	st.set_page_config(page_title="V-Controll System", page_icon="VC", layout="wide")

	st.sidebar.title("V-Controll")
	st.sidebar.caption("SaaS Contabil • Fiscal • DP")

	section = st.sidebar.radio(
		"Navegacao",
		["Dashboard", "Módulo Fiscal", "Módulo Contábil", "Módulo DP"],
		index=0,
	)

	# Dispatcher simples para manter o app.py leve e extensivel.
	routes = {
		"Dashboard": render_dashboard,
		"Módulo Fiscal": render_fiscal_module,
		"Módulo Contábil": render_contabil_module,
		"Módulo DP": render_dp_module,
	}
	routes[section]()


if __name__ == "__main__":
	main()
