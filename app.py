import streamlit as st

from app.pages.contabil import render_contabil_module
from app.pages.dashboard import render_dashboard
from app.pages.dp import render_dp_module
from modules.clientes import render_cadastro_clientes
from modules.fiscal import render_fiscal_module
from modules.produtos import render_produtos_module
from modules.relatorio_clientes import render_relatorio_clientes
from modules.sped import render_sped_module
from utils.ui_theme import apply_global_theme, render_shell_header


def main() -> None:
	"""Ponto de entrada da UI com navegacao lateral entre modulos."""
	st.set_page_config(page_title="V-Controll System", page_icon="VC", layout="wide")
	apply_global_theme()

	st.sidebar.markdown(
		"""
		<div class="vc-sidebar-brand">
			<strong>V-Controll</strong><br/>
			<span style="opacity:0.85; font-size:0.9rem;">Plataforma Fiscal e Contabil</span>
		</div>
		""",
		unsafe_allow_html=True,
	)

	section = st.sidebar.radio(
		"Navegacao",
		[
			"Dashboard",
			"Módulo Fiscal",
			"Módulo SPED Fiscal",
			"Cadastro de Produtos",
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
		"Cadastro de Produtos": render_produtos_module,
		"Módulo Contábil": render_contabil_module,
		"Módulo DP": render_dp_module,
		"Gestão de Clientes": render_cadastro_clientes,
		"Relatório de Clientes": render_relatorio_clientes,
	}
	render_shell_header(section)
	routes[section]()


if __name__ == "__main__":
	main()
