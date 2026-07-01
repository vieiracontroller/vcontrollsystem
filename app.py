import streamlit as st

from app.pages.contabil import render_contabil_module
from app.pages.dashboard import render_dashboard
from app.pages.dp import render_dp_module
from modules.apuracao import render_apuracao_module
from modules.clientes import render_cadastro_clientes
from modules.fiscal import render_fiscal_module
from modules.produtos import render_produtos_module
from modules.relatorio_clientes import render_relatorio_clientes
from modules.sped import render_sped_module
from utils.ui_theme import apply_global_theme, render_shell_header


def main() -> None:
	"""Ponto de entrada da UI com navegacao lateral entre modulos."""
	st.set_page_config(page_title="V-Controll System", page_icon="VC", layout="wide")

	st.sidebar.markdown(
		"""
		<div class="vc-sidebar-brand">
			<strong>V-Controll</strong><br/>
			<span style="opacity:0.85; font-size:0.9rem;">Plataforma Fiscal e Contabil</span>
		</div>
		""",
		unsafe_allow_html=True,
	)

	tema = st.sidebar.selectbox(
		"Aparencia",
		["Claro Institucional", "Noturno Executivo"],
		index=0,
	)
	apply_global_theme("dark" if tema == "Noturno Executivo" else "light")

	section = st.sidebar.radio(
		"Navegacao",
		[
			"01 Dashboard",
			"02 Modulo Fiscal",
			"03 Menu de Apuracao",
			"04 Modulo SPED Fiscal",
			"05 Cadastro de Produtos",
			"06 Modulo Contabil",
			"07 Modulo DP",
			"08 Gestao de Clientes",
			"09 Relatorio de Clientes",
		],
		index=0,
	)

	# Dispatcher simples para manter o app.py leve e extensivel.
	routes = {
		"01 Dashboard": render_dashboard,
		"02 Modulo Fiscal": render_fiscal_module,
		"03 Menu de Apuracao": render_apuracao_module,
		"04 Modulo SPED Fiscal": render_sped_module,
		"05 Cadastro de Produtos": render_produtos_module,
		"06 Modulo Contabil": render_contabil_module,
		"07 Modulo DP": render_dp_module,
		"08 Gestao de Clientes": render_cadastro_clientes,
		"09 Relatorio de Clientes": render_relatorio_clientes,
	}
	render_shell_header(section.split(" ", 1)[1])
	routes[section]()


if __name__ == "__main__":
	main()
