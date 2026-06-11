# DataAgent 📊

Assistente de análise de dados com IA, capaz de responder perguntas em linguagem natural sobre um banco de dados SQLite, gerando consultas SQL, gráficos (Vega-Lite) e tabelas sob demanda — tudo através de uma interface de chat construída com Streamlit.

---

## 1. Instruções de execução

### Pré-requisitos

- Python 3.10+
- Uma chave de API do Google Gemini (variável `GOOGLE_API_KEY`)
- Arquivo de banco de dados SQLite `anexo_desafio_1.db` na raiz do projeto

### Passo a passo

1. **Clone o repositório e instale as dependências:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure as variáveis de ambiente:**

   Crie um arquivo `.env` na raiz do projeto com sua chave de API:

   ```
   GOOGLE_API_KEY=sua_chave_aqui
   ```

3. **Execute a aplicação:**

   ```bash
   streamlit run app.py
   ```

4. Acesse o endereço exibido no terminal (geralmente `http://localhost:8501`).

---

## 2. Fluxo de agentes e arquitetura

### Visão geral

O projeto segue uma arquitetura de **agente único baseado em ReAct** (via `langgraph.prebuilt.create_react_agent`), apoiado por **ferramentas (tools) especializadas**. A separação de responsabilidades é feita através das tools, e não através de múltiplos agentes, uma escolha que simplifica a orquestração mantendo o raciocínio centralizado em um único loop de decisão.

O uso do **agente ReAct** permite com que o agente possa executar tarefas complexas com mais de um passo de execução, chamar as ferramentas que julgar necessário, avaliar os resultados e retornar a resposta apenas quando estiver satisfeito ou esgotar o limite de passos estabelecido.

O agente foi equipado com duas ferramentas poderosas: Uma que permite a realização de consultas no banco de dados e outra que permite a criação de gráficos. A ferramenta de gráficos é especialmente notável pois utiliza um llm secundário para gerar a SPEC do gráfico com a sintaxe vega-lite. Essa spec é então validada pela biblioteca altair e se houver erro é solicitada uma correção.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Streamlit (app.py)                      │
│  - Interface de chat                                            │
│  - Renderização de mensagens, gráficos e tabelas                │
│  - Exportação de PDF / reinício de conversa / log de queries    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ run_agent(state)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agente ReAct (agent.py)                      │
│  Modelo: Gemini (gemini-3.1-flash-lite)                         │
│  System prompt com o schema do banco + instruções de uso        │
│                                                                 │
│  Loop ReAct: o modelo decide, a cada passo, qual tool chamar    │
│  até produzir uma resposta final via `responder_usuario`        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼                   
┌────────────────────┐ ┌──────────────┐ ┌────────────────────┐
│ execute_sql_query  │ │ create_chart │ │ responder_usuario  │
│ Executa SELECT no  │ │ Gera spec    │ │ Encerra o loop com │
│ SQLite e retorna   │ │ Vega-Lite    │ │ resposta estrutu-  │
│ JSON dos resultados│ │              │ │ rada:              │
│                    │ │              │ │ content, chart,    │
│                    │ │              │ │ table, sql_queries │
└────────────────────┘ └──────────────┘ └────────────────────┘
```

### Por que essa arquitetura?

- **Agente único + tools** Permite realização de tarefas complexas com múltiplos passos e chamadas de tools, podendo inclusive chamar tools novamente em caso de erro (como query inválida).
- **Separar a geração do gráfico em uma tool com seu próprio LLM** (`create_chart`) evita sobrecarregar o prompt principal com regras detalhadas de Vega-Lite, e permite usar uma temperatura mais baixa (`0.0`) especificamente para essa tarefa, que exige saída JSON precisa.
- **Vega-lite para geração de gráficos** é uma ferramenta que permite a declaração de todas as especificações do gráfico em formato json, sendo ideal para llms. Além disso streamlit possui uma função nativa para renderizar os gráficos nesse formato.
- **Resposta final estruturada via tool** (`responder_usuario`) permite que o streamlit consiga acessar as informações de texto, de gráfico e de tabela da resposta de forma estruturada, evitando problemas de parsing.
- **Schema dinâmico** o schema do banco de dados é verificado dinamicamente, de forma que é possível plugar qualquer banco sqlite na ferramenta e tudo irá funcionar normalmente.

---

## 3. Exemplos de consultas

`Crie um gráfico de linha do faturamento` 
`Quais foram os 5 produtos mais vendidos?`
`Mostre uma tabela com todas as transações de junho de 2025`
`Qual a participação de cada categoria no faturamento total?`
`Compare a performance das campanhas`
`Quais são as cidades com mais compras?`

> 💡 Para reproduzir esses testes, basta digitar as perguntas na caixa de chat da interface e observar a resposta, os gráficos/tabelas gerados e as consultas SQL utilizadas.

---

## 4. Sugestões de melhorias e extensões

- **Gráficos mais avançados**: permitir que o agente acesse toda a documentação do vega-lite via RAG, para poder gerar gráficos mais complexos.
- **Suporte a múltiplos bancos**: abstrair `database.py` com SQLAlchemy permitiria trocar SQLite por Postgres/MySQL sem alterar `agent.py`.
- **Histórico persistente**: salvar conversas em disco/banco para que o usuário possa retomar sessões anteriores após recarregar a página.
- **Edição/refinamento de gráficos**: permitir que o usuário peça ajustes ("troque para gráfico de barras", "use cores diferentes") reaproveitando os dados já consultados, sem nova ida ao banco.
- **Geração de relatórios**: ao invés de simplesmente exportar a conversa em PDF gerar um relatório contendo gráficos, tabelas e comentários sobre os dados seguindo um template da empresa.