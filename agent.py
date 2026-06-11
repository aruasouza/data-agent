from dotenv import load_dotenv
load_dotenv()

import json
from datetime import date
from typing import Annotated, Any, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages

from database import get_schema, run_sql_query
from langchain_core.tools import tool

from typing import Optional
from pydantic import BaseModel, Field

class Resposta(BaseModel):
    content: str = Field(description="Resposta em texto para o usuário.")
    chart: Optional[str] = Field(description="JSON do gráfico em formato vega-lite, se aplicável.", default=None)
    table: Optional[str] = Field(description="CSV com os dados a serem exibidos em formato de tabela, se aplicável.", default=None)
    sql_queries: Optional[str] = Field(description="Consultas SQL executadas, se aplicável.", default=None)

class Chart(BaseModel):
    chart: str = Field(description="Declaração do gráfico no formato JSON utilizando a sintaxe vega-lite.")
    
@tool
def execute_sql_query(query: str) -> str:
    """Executa uma consulta SQL no banco de dados e retorna os resultados."""
    try:
        result = run_sql_query(query)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao executar consulta: {str(e)}"
    
@tool
def create_chart(prompt: str, data: str) -> str:
    """Cria um gráfico no formato json com a sintaxe do vega-lite com base no prompt e nos dados fornecidos"""
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.0).with_structured_output(Chart)
    with open('vega_skill.txt','r',encoding='utf-8') as f:
        examples = f.read()
    mensagens = [
        SystemMessage(content="Você é um especialista em criar gráficos em formato vega-lite com base em dados e solicitações do usuário. Crie gráficos com lindo design e que tragam bons insights para o usuário."),
        SystemMessage(content=f"Exemplos de gráficos com a sintaxe vega-lite: {examples}"),
        SystemMessage(content='''O template padrão é:
            {
            "data": {{ "values": [] }},
            "mark": "bar",
            "encoding": {{
                "x": {{ "field": "", "type": "nominal", "title": "" }},
                "y": {{ "field": "", "type": "quantitative", "title": "" }}
            }}
            }'''),
        HumanMessage(content=f"Crie um gráfico vega-lite baseado neste prompt: {prompt} e estes dados: {data}")
    ]
    chart: Chart = llm.invoke(mensagens)
    return chart.chart

    
@tool
def responder_usuario(resposta: Resposta) -> str:
    """Ferramenta para fornecer respostas ao usuário."""
    return f"Resposta ao usuário: {resposta.content}"

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    last_response: dict | None

def run_agent(state: dict) -> dict:
    schema = get_schema()
    
    system_prompt = f"""Você é um assistente especializado em consultas SQL.
Você tem acesso a um banco de dados com o seguinte esquema:

{schema}

Sua tarefa é:
1. Analisar perguntas dos usuários sobre o banco de dados
2. Gerar consultas SQL apropriadas para responder essas perguntas
3. Executar as consultas usando a ferramenta run_sql_query
4. Interpretar os resultados e fornecer respostas claras e úteis
5. Se aplicável, crie um gráfico usando a ferramenta create_chart, pense em gráficos que tragam insights úteis para o usuário. Pense no gráfico de forma mais alto nível e deixe que a ferramenta de gráficos desenvolva o design com mais detalhes.
6. Se o usuário pedir uma tabela, ou se uma tabela for a melhor forma de apresentar os dados (ex: listagem de registros), preencha o campo `table` da resposta em formato csv. Não use chart e table ao mesmo tempo, a menos que o usuário peça explicitamente os dois.

Sempre gere consultas SQL válidas e seguras. Se não tiver certeza sobre como responder, peça esclarecimentos.

IMPORTANTE: Sua resposta final SEMPRE deve ser entregue através da ferramenta 
`responder_usuario`. Nunca responda diretamente em texto livre — 
chame `responder_usuario` com o conteúdo, gráfico (se houver) e consultas SQL executadas."""

    tools = [execute_sql_query, responder_usuario, create_chart]
    agent = create_react_agent(
        name="analista-de-dados",
        model=ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite",
            temperature=0.3,
        ),
        tools=tools,
    )

    input_state = state.copy()
    input_state["messages"] = [SystemMessage(content=system_prompt)] + input_state["messages"]

    response = agent.invoke(input_state, config={"recursion_limit": 20})

    resposta_estruturada = {
    "content": "",
    "chart": None,
    "sql_queries": []
}

    found_tool_response = False
    for msg in reversed(response["messages"]):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call["name"] == "responder_usuario":
                    resposta_estruturada = tool_call["args"]["resposta"]
                    found_tool_response = True
                    break
        if found_tool_response:
            break

    if not found_tool_response:
        for msg in reversed(response["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                resposta_estruturada["content"] = msg.content
                break

    response_text = resposta_estruturada.get('content', '')
    return {"messages": [AIMessage(content=response_text)], "last_response": resposta_estruturada}

if __name__ == '__main__':
    prompt_teste = 'Crie um gráfico de linha do faturamento no último ano'
    state = {"messages": [HumanMessage(content=prompt_teste)], "last_response": None}
    response = run_agent(state)
    print(response)