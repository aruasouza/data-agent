import io
import json
import time
import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agent import run_agent
from utils import build_pdf

DELAY = .05

# ─── Configuração da página ───────────────────────────────────────────────────

st.set_page_config(
    page_title="DataAgent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS personalizado ────────────────────────────────────────────────────────

with open("style.css", "r") as f:
    st.markdown(f'<style>\n{f.read()}\n</style>', unsafe_allow_html=True)


# ─── Session state init ───────────────────────────────────────────────────────

def delay(x):
    time.sleep(DELAY)
    return x

def init_session():
    if "agent_state" not in st.session_state:
        st.session_state.agent_state = {'messages':[]}
    if "display_messages" not in st.session_state:
        st.session_state.display_messages = []
    if "charts" not in st.session_state:
        st.session_state.charts = []
    if "tables" not in st.session_state:
        st.session_state.tables = []


# ─── Chart renderer ───────────────────────────────────────────────────────────

def render_chart(chart_data: str):
    data = json.loads(chart_data)
    st.vega_lite_chart(data, width='stretch')


def render_table(table_data: str):
    try:
        df = pd.read_csv(io.StringIO(table_data))
        st.dataframe(df, width='stretch', hide_index=True)
    except Exception:
        st.warning("Não foi possível exibir a tabela.")


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("#### 📊 DataAgent")

        st.divider()

        # Botão de reiniciar chat
        if st.button("🔄 Reiniciar conversa", width='stretch'):
            st.session_state.agent_state = {'messages': []}
            st.session_state.display_messages = []
            st.session_state.charts = []
            st.session_state.tables = []
            st.session_state.pop("stream_response", None)
            st.rerun()

        # Botão de exportar PDF
        if st.session_state.display_messages:
            pdf_bytes = build_pdf()
            st.download_button(
                label="📄 Exportar conversa em PDF",
                data=pdf_bytes,
                file_name="dataagent_conversa.pdf",
                mime="application/pdf",
                width='stretch',
            )
        else:
            st.button("📄 Exportar conversa em PDF", width='stretch', disabled=True)


# ─── Chat area ────────────────────────────────────────────────────────────────

def render_chat():

    # Mensagens
    msgs = st.session_state.display_messages
    charts = st.session_state.charts

    chat_container = st.container(height=500,border=False,horizontal_alignment='center')
    with chat_container:
        if not msgs:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#4a5568">
                <div style="font-size:3rem">📊</div>
                <h3 style="color:#6b7280;font-weight:400">Bem-vindo ao DataAgent</h3>
                <p>Seu assistente de análise de dados pessoal com IA.<br>
                Envie uma mensagem para começar.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            chart_idx = 0
            table_idx = 0
            tables = st.session_state.tables
            l = len(msgs) - 1
            for i, msg in enumerate(msgs):
                if msg["role"] == "user":
                    message = st.chat_message(name='user')
                    message.text(msg['content'])
                else:
                    message = st.chat_message(name='assistant')
                    if (i == l) and st.session_state.get('stream_response'):
                        message.write_stream(map(lambda x: delay(x) + ' ',msg['content'].replace('$','\$').split()))
                        st.session_state.stream_response = False
                    else:
                        message.write(msg['content'].replace('$','\$'))

                    if msg.get("has_chart") and chart_idx < len(charts):
                        render_chart(charts[chart_idx])
                        chart_idx += 1
                    if msg.get("has_table") and table_idx < len(tables):
                        render_table(tables[table_idx])
                        table_idx += 1

                    sql_queries = msg.get("sql_queries")
                    if sql_queries:
                        with st.expander("🗄️ Consultas SQL"):
                            for q in sql_queries:
                                st.code(q, language="sql")
    return chat_container


# ─── Input area ──────────────────────────────────────────────────────────────

def handle_input(user_input: str, chat_container):
    if not user_input.strip():
        return

    # Adiciona mensagem do usuário ao display
    st.session_state.display_messages.append({"role": "user", "content": user_input})

    # Atualiza estado com mensagem do usuário
    current_state = st.session_state.agent_state
    current_state["messages"] = current_state["messages"] + [HumanMessage(content=user_input)]

    # Invoca o grafo
    with chat_container.spinner("Pensando..."):
        result = run_agent(current_state)

    # Atualiza estado
    st.session_state.agent_state = result

    # Extrai resposta do agente
    chart_request = result.get('last_response').get('chart')
    table_request = result.get('last_response').get('table')
    sql_queries = result.get('last_response').get('sql_queries') or []
    if isinstance(sql_queries, str):
        sql_queries = [sql_queries]

    last_ai_msg = None
    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage):
            last_ai_msg = m.content
            break

    if last_ai_msg:
        has_chart = chart_request is not None
        has_table = table_request is not None
        st.session_state.display_messages.append({
            "role": "assistant",
            "content": last_ai_msg,
            "has_chart": has_chart,
            "has_table": has_table,
            "sql_queries": sql_queries,
        })
        if has_chart:
            st.session_state.charts.append(chart_request)
        if has_table:
            st.session_state.tables.append(table_request)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_session()
    render_sidebar()

    main_col, _ = st.columns([1, 0.001])
    with main_col:
        chat_container = render_chat()
        msgs = st.session_state.display_messages

        # Input do usuário
        if not msgs:
            placeholder = chat_container.empty()
            mini_cont = placeholder.container(width=550,border=False)
            user_input = mini_cont.chat_input(
                key="user_input",
                placeholder="Digite sua mensagem... (ex: 'Crie um gráfico de linha do faturamento no último ano')",
            )
        else:
            user_input = st.chat_input(
                key="user_input",
                placeholder="Digite sua mensagem... (ex: 'Crie um gráfico de linha do faturamento no último ano')",
            )
        # Processa input
        if user_input:
            if not msgs:
                placeholder.empty()
            message = chat_container.chat_message(name='user')
            message.write(user_input)
            st.session_state.stream_response = True
            handle_input(user_input,chat_container)
            st.rerun()

if __name__ == "__main__":
    main()