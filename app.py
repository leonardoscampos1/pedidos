import streamlit as st
import pandas as pd
import sqlite3

# -----------------------
# 🔗 Links das planilhas
# -----------------------
URL_ESTOQUE = "https://hbox.houseti.com.br/s/vyXQh7YFvlBwklN/download"
URL_CLIENTES = "https://hbox.houseti.com.br/s/0sPqxMVBDuboOZk/download"

# -----------------------
# 📖 Funções de leitura com cache
# -----------------------
@st.cache_data
def carregar_dados():
    df = pd.read_excel(URL_ESTOQUE)
    df.columns = df.columns.str.upper()
    df['CODPROD_STR'] = df['CODPROD'].astype(str)
    return df

@st.cache_data
def carregar_clientes():
    excel_clientes = pd.ExcelFile(URL_CLIENTES)
    clientes_brasil = pd.read_excel(excel_clientes, sheet_name="Clientes_Brasil")
    clientes_crc = pd.read_excel(excel_clientes, sheet_name="Clientes_CRC")
    for df in [clientes_brasil, clientes_crc]:
        df.columns = df.columns.str.upper()
        df['CODCLI_STR'] = df['CODCLI'].astype(str)
    return clientes_brasil, clientes_crc

# -----------------------
# Inicializa session_state
# -----------------------
if "dados" not in st.session_state:
    st.session_state.dados = carregar_dados()
if "clientes_brasil" not in st.session_state or "clientes_crc" not in st.session_state:
    st.session_state.clientes_brasil, st.session_state.clientes_crc = carregar_clientes()

# -----------------------
# Conexão SQLite
# -----------------------
conn = sqlite3.connect("pedidos.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    codigo INTEGER,
    produto TEXT,
    quantidade INTEGER,
    filial TEXT,
    sistema TEXT,
    cliente_codigo TEXT
)
""")
conn.commit()

# -----------------------
# Sidebar: Configurações
# -----------------------
st.sidebar.header("Configurações")

# Filial
filial_opcao = st.sidebar.selectbox("Selecione a filial:", ["1", "2", "3", "4"])
st.session_state.filial = filial_opcao

# Sistema
sistema_opcao = st.sidebar.selectbox("Selecione o sistema:", ["BRASIL", "CRC"])
st.session_state.sistema = sistema_opcao

# Cliente filtrado pelo sistema
st.sidebar.header("Cliente")
df_clientes = (
    st.session_state.clientes_brasil
    if st.session_state.sistema == "BRASIL"
    else st.session_state.clientes_crc
)
opcoes_clientes = [
    f"{row['CODCLI']} - {row['CLIENTE']}"
    for row in df_clientes.to_dict("records")
]
cliente_selecionado = st.sidebar.selectbox("Selecione o cliente:", opcoes_clientes)
st.session_state.cliente_codigo = cliente_selecionado.split(" - ")[0]  # apenas código
st.session_state.cliente_nome = " - ".join(
    cliente_selecionado.split(" - ")[1:]
)  # nome completo

# -----------------------
# Interface principal
# -----------------------
st.title("🛒 Sistema de Pedidos")
st.markdown("<p color='gray' style='font-size:16px;'>Por Leonardo Campos.</p>", unsafe_allow_html=True)

# Pesquisa de produtos
pesquisa = st.text_input("Digite o nome ou código do produto:")

if pesquisa:
    resultados = st.session_state.dados[
        st.session_state.dados['DESCRICAO'].str.contains(pesquisa, case=False, na=False)
        | st.session_state.dados['CODPROD_STR'].str.contains(pesquisa, case=False, na=False)
    ]

    if not resultados.empty:
        resultados_unicos = resultados.drop_duplicates(subset=['CODPROD', 'DESCRICAO'])
        produtos_opcoes = [
            f"{row['CODPROD']} - {row['DESCRICAO']}"
            for row in resultados_unicos.to_dict('records')
        ]

        produto_selecionado = st.selectbox("Selecione o produto:", produtos_opcoes)
        cod_escolhido = produto_selecionado.split(" - ")[0]
        descricao_escolhida = " - ".join(produto_selecionado.split(" - ")[1:])
        quantidade = st.number_input("Quantidade:", min_value=1, step=1)

        if st.button("Adicionar ao Pedido"):
            c.execute(
                "INSERT INTO pedidos VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(cod_escolhido),
                    descricao_escolhida,
                    quantidade,
                    st.session_state.filial,
                    st.session_state.sistema,
                    st.session_state.cliente_codigo,
                ),
            )
            conn.commit()
            st.success(f"✅ {quantidade}x {descricao_escolhida} adicionado ao pedido!")

# -----------------------
# Mostrar pedidos filtrados
# -----------------------
st.subheader("📁 Pedidos salvos")

df_pedidos = pd.read_sql(
    "SELECT * FROM pedidos WHERE sistema=? AND filial=? AND cliente_codigo=?",
    conn,
    params=(st.session_state.sistema, st.session_state.filial, st.session_state.cliente_codigo),
)

if not df_pedidos.empty:
    st.dataframe(df_pedidos.tail(100))

    # Download Excel com nome do cliente e filial
    arquivo_excel = f"pedidos_{st.session_state.cliente_nome}_Filial{st.session_state.filial}.xlsx"
    df_pedidos.to_excel(arquivo_excel, index=False)

    # Remover produto
    produto_remover = st.selectbox(
        "Selecione um produto para remover:",
        df_pedidos["codigo"].astype(str) + " - " + df_pedidos["produto"],
    )
    cod_remover = int(produto_remover.split(" - ")[0])

    if st.button("🗑 Remover produto"):
        c.execute(
            "DELETE FROM pedidos WHERE codigo=? AND sistema=? AND filial=? AND cliente_codigo=?",
            (
                cod_remover,
                st.session_state.sistema,
                st.session_state.filial,
                st.session_state.cliente_codigo,
            ),
        )
        conn.commit()
        st.success(f"Produto {produto_remover} removido com sucesso!")
        st.rerun()

    # ✅ Botão de download — agora no nível certo
    st.download_button(
        label="⬇️ Baixar pedidos em Excel",
        data=open(arquivo_excel, "rb").read(),
        file_name=arquivo_excel,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Nenhum pedido salvo para este cliente/filial/sistema.")
