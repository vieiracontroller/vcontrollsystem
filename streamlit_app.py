import streamlit as st

st.set_page_config(
	page_title="V-Controll | Painel Contabil",
	page_icon="VC",
	layout="wide",
)

# Ajuste estes valores para refletir exatamente a paleta do seu Painel principal.
PALETA = {
	"bg": "#F4F7FB",
	"surface": "#FFFFFF",
	"text": "#0E1A2B",
	"muted": "#5B6B84",
	"primary": "#0F4C81",
	"secondary": "#1B8A7A",
	"accent": "#F2A93B",
	"danger": "#B23A48",
	"border": "#D8E1EE",
}

st.markdown(
	f"""
	<style>
	:root {{
		--bg: {PALETA['bg']};
		--surface: {PALETA['surface']};
		--text: {PALETA['text']};
		--muted: {PALETA['muted']};
		--primary: {PALETA['primary']};
		--secondary: {PALETA['secondary']};
		--accent: {PALETA['accent']};
		--danger: {PALETA['danger']};
		--border: {PALETA['border']};
	}}

	.stApp {{
		background:
			radial-gradient(circle at 10% 0%, #ffffff 0%, var(--bg) 42%),
			linear-gradient(140deg, #ffffff 0%, var(--bg) 100%);
		color: var(--text);
	}}

	.hero {{
		background: linear-gradient(120deg, var(--primary) 0%, var(--secondary) 100%);
		color: #ffffff;
		padding: 1.4rem;
		border-radius: 16px;
		margin-bottom: 1rem;
		box-shadow: 0 12px 28px rgba(15, 76, 129, 0.20);
	}}

	.hero h1 {{
		margin: 0;
		font-size: 2rem;
	}}

	.hero p {{
		margin: 0.4rem 0 0;
		color: #e8f2ff;
	}}

	.kpi-card {{
		background: var(--surface);
		border: 1px solid var(--border);
		border-left: 6px solid var(--primary);
		border-radius: 14px;
		padding: 1rem;
		min-height: 110px;
		box-shadow: 0 8px 20px rgba(14, 26, 43, 0.06);
	}}

	.kpi-title {{
		margin: 0;
		color: var(--muted);
		font-size: 0.92rem;
	}}

	.kpi-value {{
		margin: 0.3rem 0 0;
		font-size: 1.45rem;
		font-weight: 700;
		color: var(--text);
	}}

	.section-title {{
		margin-top: 0.3rem;
		margin-bottom: 0.4rem;
		color: var(--text);
		font-size: 1.15rem;
		font-weight: 700;
	}}

	.panel-box {{
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 14px;
		padding: 1rem;
		box-shadow: 0 8px 20px rgba(14, 26, 43, 0.05);
	}}

	.status-ok {{ color: var(--secondary); font-weight: 700; }}
	.status-attention {{ color: var(--accent); font-weight: 700; }}
	.status-risk {{ color: var(--danger); font-weight: 700; }}

	.stButton > button {{
		background: linear-gradient(120deg, var(--primary) 0%, var(--secondary) 100%);
		color: #ffffff;
		border: none;
		border-radius: 10px;
		font-weight: 700;
	}}
	</style>
	""",
	unsafe_allow_html=True,
)

st.markdown(
	"""
	<div class="hero">
		<h1>V-Controll System</h1>
		<p>Painel contabil com visao rapida de faturamento, pendencias e saude financeira.</p>
	</div>
	""",
	unsafe_allow_html=True,
)

st.sidebar.header("Filtros")
mes = st.sidebar.selectbox(
	"Competencia",
	["Jun/2026", "Mai/2026", "Abr/2026"],
	index=0,
)
empresa = st.sidebar.selectbox(
	"Empresa",
	["Grupo Vieira", "Cliente A", "Cliente B"],
	index=0,
)

st.sidebar.caption(f"Visualizando: {empresa} - {mes}")

col1, col2, col3, col4 = st.columns(4)

with col1:
	st.markdown(
		"""
		<div class="kpi-card">
			<p class="kpi-title">Receita no mes</p>
			<p class="kpi-value">R$ 124.830,00</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

with col2:
	st.markdown(
		"""
		<div class="kpi-card" style="border-left-color: var(--secondary);">
			<p class="kpi-title">Despesas no mes</p>
			<p class="kpi-value">R$ 78.420,00</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

with col3:
	st.markdown(
		"""
		<div class="kpi-card" style="border-left-color: var(--accent);">
			<p class="kpi-title">Impostos previstos</p>
			<p class="kpi-value">R$ 18.350,00</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

with col4:
	st.markdown(
		"""
		<div class="kpi-card" style="border-left-color: var(--danger);">
			<p class="kpi-title">Pendencias</p>
			<p class="kpi-value">03 itens</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

left, right = st.columns([1.2, 1])

with left:
	st.markdown('<p class="section-title">Lancamentos recentes</p>', unsafe_allow_html=True)
	st.markdown('<div class="panel-box">', unsafe_allow_html=True)
	st.dataframe(
		[
			{"Data": "28/06/2026", "Descricao": "Honorarios", "Tipo": "Entrada", "Valor": "R$ 7.500,00"},
			{"Data": "27/06/2026", "Descricao": "Folha de pagamento", "Tipo": "Saida", "Valor": "R$ 12.240,00"},
			{"Data": "26/06/2026", "Descricao": "Imposto DAS", "Tipo": "Saida", "Valor": "R$ 2.180,00"},
			{"Data": "25/06/2026", "Descricao": "Consultoria", "Tipo": "Entrada", "Valor": "R$ 4.900,00"},
		],
		use_container_width=True,
		hide_index=True,
	)
	st.markdown('</div>', unsafe_allow_html=True)

with right:
	st.markdown('<p class="section-title">Checklist contabil</p>', unsafe_allow_html=True)
	st.markdown(
		"""
		<div class="panel-box">
			<p><span class="status-ok">Concluido</span> - Conciliacao bancaria</p>
			<p><span class="status-attention">Em andamento</span> - Fechamento fiscal</p>
			<p><span class="status-risk">Pendente</span> - Validacao de notas de servico</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

st.markdown('<p class="section-title">Novo lancamento</p>', unsafe_allow_html=True)
with st.form("form_lancamento"):
	c1, c2, c3 = st.columns(3)
	with c1:
		descricao = st.text_input("Descricao")
	with c2:
		valor = st.number_input("Valor (R$)", min_value=0.0, step=100.0)
	with c3:
		tipo = st.selectbox("Tipo", ["Entrada", "Saida"])

	submitted = st.form_submit_button("Salvar lancamento")

if submitted:
	st.success(f"Lancamento registrado: {descricao} ({tipo}) - R$ {valor:,.2f}")
