import streamlit as st

from app.pages.contabil import render_contabil_module
from app.pages.dashboard import render_dashboard
from app.pages.dp import render_dp_module
from modules.clientes import render_cadastro_clientes
from modules.fiscal import render_fiscal_module
from modules.relatorio_clientes import render_relatorio_clientes
from modules.sped import render_sped_module


def main() -> None:
	"""Ponto de entrada da UI com navegacao lateral entre modulos."""
	st.set_page_config(page_title="V-Controll System", page_icon="VC", layout="wide")

	st.sidebar.title("V-Controll")
	st.sidebar.caption("SaaS Contabil • Fiscal • DP")

	section = st.sidebar.radio(
		"Navegacao",
		[
			"Dashboard",
			"Módulo Fiscal",
			"Módulo SPED Fiscal",
			"Módulo Contábil",
			"Módulo DP",
			"Gestão de Clientes",
			"Relatório de Clientes",
		],
		index=0,
	)

	# Dispatcher simples para manter o app.py leve e extensivel.
	routes = {
		"Dashboard": render_dashboard,
		"Módulo Fiscal": render_fiscal_module,
		"Módulo SPED Fiscal": render_sped_module,
		"Módulo Contábil": render_contabil_module,
		"Módulo DP": render_dp_module,
		"Gestão de Clientes": render_cadastro_clientes,
		"Relatório de Clientes": render_relatorio_clientes,
	}
	routes[section]()


if __name__ == "__main__":
	main()
