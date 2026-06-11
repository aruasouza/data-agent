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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #0f1117;
    color: #e8eaf0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #161b27 !important;
    border-right: 1px solid #2a2f3e;
}

/* Chat messages */
.user-bubble {
    background: #1e3a5f;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    margin: 8px 0;
    margin-left: 20%;
    color: #d0e8ff;
    font-size: 0.95rem;
    line-height: 1.5;
}

.ai-bubble {
    background: #1a2035;
    border: 1px solid #2a3050;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    margin: 8px 0;
    margin-right: 15%;
    color: #c8d8f0;
    font-size: 0.95rem;
    line-height: 1.6;
}

.agent-label {
    font-size: 0.75rem;
    color: #4a90d9;
    font-weight: 600;
    margin-bottom: 4px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.user-label {
    font-size: 0.75rem;
    color: #7ab8f5;
    font-weight: 600;
    margin-bottom: 4px;
    text-align: right;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* Header */
.main-header {
    background: linear-gradient(135deg, #1a2a4a 0%, #0d1a2e 100%);
    border-bottom: 1px solid #2a3a5a;
    padding: 16px 24px;
    margin-bottom: 0;
}

/* Metric cards */
.metric-card {
    background: #1a2035;
    border: 1px solid #2a3050;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
}

/* Input area */
.stTextInput > div > div > input {
    background: #1a2035 !important;
    border: 1px solid #2a3a5a !important;
    border-radius: 24px !important;
    color: #e8eaf0 !important;
    padding: 12px 20px !important;
    font-family: 'DM Sans', sans-serif !important;
}

.stButton > button {
    background: linear-gradient(135deg, #1e5fa8, #0d3a6e) !important;
    color: white !important;
    border: none !important;
    border-radius: 24px !important;
    padding: 10px 24px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 15px rgba(30, 95, 168, 0.4) !important;
}

/* Status badge */
.status-auth {
    display: inline-block;
    background: #0d3a1e;
    color: #4ade80;
    border: 1px solid #166534;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8rem;
    font-weight: 500;
}

.status-unauth {
    display: inline-block;
    background: #3a1a0d;
    color: #fb923c;
    border: 1px solid #7c2d12;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8rem;
    font-weight: 500;
}

hr { border-color: #2a3050; }

/* Scrollable chat area */
.chat-container {
    max-height: 60vh;
    overflow-y: auto;
    padding-right: 8px;
}
</style>
""", unsafe_allow_html=True)


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
    if "last_sql_queries" not in st.session_state:
        st.session_state.last_sql_queries = []


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
            st.session_state.last_sql_queries = []
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

        st.divider()

        # Janela com as queries da última requisição
        st.markdown("##### 🗄️ Consultas SQL (última requisição)")
        queries = st.session_state.last_sql_queries
        if queries:
            for i, q in enumerate(queries, start=1):
                st.code(q, language="sql")
        else:
            st.caption("Nenhuma consulta executada ainda.")

# ─── Chat area ────────────────────────────────────────────────────────────────

def render_chat():

    # Mensagens
    msgs = st.session_state.display_messages
    charts = st.session_state.charts

    chat_container = st.container(height=400)
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
    st.session_state.last_sql_queries = sql_queries

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

        # Atalho de shortcut
        if "shortcut_prompt" in st.session_state:
            prompt = st.session_state.pop("shortcut_prompt")
            message = chat_container.chat_message(name='user')
            message.write(prompt)
            st.session_state.stream_response = True
            handle_input(prompt,chat_container)
            st.rerun()

        # Input do usuário
        user_input = st.chat_input(
            key="user_input",
            placeholder="Digite sua mensagem... (ex: 'Gastei R$45 no almoço hoje')",
        )
        # Processa input
        if user_input:
            message = chat_container.chat_message(name='user')
            message.write(user_input)
            st.session_state.stream_response = True
            handle_input(user_input,chat_container)
            st.rerun()

if __name__ == "__main__":
    main()