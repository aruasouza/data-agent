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

3. **Confirme que os arquivos de apoio estão presentes:**

   - `anexo_desafio_1.db` — banco de dados SQLite com os dados a serem consultados
   - `vega_skill.txt` — exemplos e regras de sintaxe Vega-Lite usados pelo agente para gerar gráficos

4. **Execute a aplicação:**

   ```bash
   streamlit run app.py
   ```

5. Acesse o endereço exibido no terminal (geralmente `http://localhost:8501`).

### Testando o agente isoladamente (sem interface)

É possível rodar o agente diretamente pelo terminal, sem a interface Streamlit:

```bash
python agent.py
```

Isso executa o prompt de teste definido no bloco `if __name__ == '__main__':` de `agent.py`.

---

## 2. Fluxo de agentes e arquitetura

### Visão geral

O projeto segue uma arquitetura de **agente único baseado em ReAct** (via `langgraph.prebuilt.create_react_agent`), apoiado por **ferramentas (tools) especializadas**. A separação de responsabilidades é feita através das tools, e não através de múltiplos agentes — uma escolha que simplifica a orquestração mantendo o raciocínio centralizado em um único loop de decisão.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Streamlit (app.py)                       │
│  - Interface de chat                                              │
│  - Renderização de mensagens, gráficos e tabelas                 │
│  - Exportação de PDF / reinício de conversa / log de queries     │
└───────────────────────────┬───────────────────────────────────────┘
                             │ run_agent(state)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agente ReAct (agent.py)                       │
│  Modelo: Gemini (gemini-3.1-flash-lite)                          │
│  System prompt com o schema do banco + instruções de uso         │
│                                                                    │
│  Loop ReAct: o modelo decide, a cada passo, qual tool chamar     │
│  até produzir uma resposta final via `responder_usuario`         │
└───────────────────────────┬───────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬───────────────────┐
        ▼                    ▼                    ▼                    ▼
┌───────────────────┐ ┌──────────────┐ ┌────────────────────┐ ┌──────────────────┐
│ execute_sql_query  │ │ create_chart │ │  responder_usuario  │ │   (database.py)   │
│ Executa SELECT no  │ │ Gera spec    │ │ Encerra o loop com  │ │  get_schema()      │
│ SQLite e retorna   │ │ Vega-Lite    │ │ resposta estrutu-   │ │  run_sql_query()   │
│ JSON dos resultados│ │ (LLM auxiliar│ │ rada (Resposta):    │ │  (somente SELECT)  │
│                    │ │ + exemplos)  │ │ content, chart,     │ │                    │
│                    │ │              │ │ table, sql_queries  │ │                    │
└───────────────────┘ └──────────────┘ └────────────────────┘ └──────────────────┘
```

### Componentes principais

#### `agent.py`

- **`get_schema()` / `run_sql_query()`** (de `database.py`): fornecem ao LLM o esquema do banco no início da conversa e executam consultas `SELECT` de forma segura — qualquer outra operação (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.) é bloqueada antes mesmo de chegar ao SQLite.

- **`execute_sql_query`** (tool): encapsula `run_sql_query`, retornando os resultados em JSON para o agente interpretar.

- **`create_chart`** (tool): usa um segundo LLM (com `with_structured_output(Chart)`), alimentado por exemplos de specs Vega-Lite válidos (`vega_skill.txt`) e por um template padrão, para transformar dados tabulares em uma especificação de gráfico pronta para renderização.

- **`responder_usuario`** (tool): é a "porta de saída" do agente. Toda resposta final deve passar por ela, retornando um objeto `Resposta` estruturado com:
  - `content`: texto da resposta;
  - `chart`: spec Vega-Lite (opcional);
  - `table`: dados em formato de lista de objetos JSON, para exibição em tabela (opcional);
  - `sql_queries`: consultas SQL executadas (opcional).

  Forçar a resposta final através de uma tool estruturada (em vez de texto livre) garante que a interface sempre receba dados em um formato previsível, podendo renderizar gráficos, tabelas e logs de consultas de forma consistente.

- **`run_agent(state)`**: monta o prompt do sistema (com o schema atualizado do banco), invoca o grafo do agente com `recursion_limit` definido, e percorre as mensagens retornadas em ordem reversa procurando a chamada à tool `responder_usuario`. Caso o modelo não a tenha chamado (comportamento ocasional de modelos menores), há um *fallback* que extrai o texto da última `AIMessage` como resposta.

#### `app.py`

- Mantém o estado da conversa (`agent_state`, `display_messages`, `charts`, `tables`, `last_sql_queries`) na sessão do Streamlit.
- A cada mensagem do usuário, chama `run_agent` passando o histórico completo de mensagens (`HumanMessage`/`AIMessage`), preservando contexto entre turnos.
- Renderiza, além do texto, gráficos (`st.vega_lite_chart`) e tabelas (`st.dataframe`) quando presentes na resposta estruturada.
- Funcionalidades auxiliares:
  - **Reiniciar conversa**: limpa todo o estado da sessão.
  - **Exportar em PDF**: usa `vl-convert-python` para rasterizar os gráficos Vega-Lite em PNG e `reportlab` para montar um PDF com o histórico completo (texto, gráficos e tabelas).
  - **Painel de consultas SQL**: exibe, na barra lateral, as queries executadas na última requisição — útil para depuração e transparência sobre como o agente chegou à resposta.

### Por que essa arquitetura?

- **Agente único + tools** é mais simples de depurar e manter do que múltiplos agentes coordenados, e é suficiente para o escopo do problema (consultas a um único banco de dados).
- **Separar a geração do gráfico em uma tool com seu próprio LLM** (`create_chart`) evita sobrecarregar o prompt principal com regras detalhadas de Vega-Lite, e permite usar uma temperatura mais baixa (`0.0`) especificamente para essa tarefa, que exige saída JSON precisa.
- **Resposta final estruturada via tool** (`responder_usuario`) desacopla "o que o modelo pensa" de "o que é exibido ao usuário", evitando que texto de raciocínio intermediário vaze para a interface.
- **Validação de SQL na camada de banco de dados** (`database.py`) garante uma camada extra de segurança independente do comportamento do LLM: mesmo que o modelo gere uma query perigosa, ela é bloqueada antes da execução.

---

## 3. Exemplos de consultas testadas

As perguntas abaixo foram usadas para validar o fluxo completo (geração de SQL → execução → interpretação → resposta/gráfico/tabela):

| Pergunta do usuário | Comportamento esperado |
|---|---|
| `Crie um gráfico de linha do faturamento no último ano` | Agente gera SQL agregando faturamento por mês, executa, e chama `create_chart` para produzir um gráfico de linha (Vega-Lite). |
| `Quais foram os 5 produtos mais vendidos?` | Agente gera um `SELECT ... ORDER BY ... LIMIT 5`, e responde com texto resumindo o resultado (com ou sem gráfico de barras). |
| `Mostre uma tabela com todas as transações de junho de 2025` | Agente preenche o campo `table` com os registros retornados, exibidos como `st.dataframe` na interface. |
| `Qual a participação de cada categoria no faturamento total?` | Agente agrega os dados por categoria e gera um gráfico de pizza/rosca (`mark: arc`). |
| `Compare o faturamento mensal entre as filiais` | Agente gera um gráfico de linhas múltiplas, uma série por filial (`encoding.color`). |
| `Quantos registros existem na tabela de vendas?` | Agente executa `SELECT COUNT(*)` e responde apenas em texto, sem gráfico nem tabela. |
| `Apague todos os registros de vendas de 2024` | **Bloqueado**: `run_sql_query` rejeita qualquer query que não comece com `SELECT`, e o agente informa ao usuário que a operação não é permitida. |
| `Qual é a capital da França?` | Pergunta fora do escopo: o agente deve identificar que não está relacionada ao banco de dados e pedir esclarecimento ou informar a limitação. |

> 💡 Para reproduzir esses testes, basta digitar as perguntas na caixa de chat da interface e observar a resposta, os gráficos/tabelas gerados e o painel de "Consultas SQL" na barra lateral.

---

## 4. Sugestões de melhorias e extensões

### Robustez e qualidade das respostas

- **Garantir resposta estruturada sempre**: mesmo com o fallback atual, modelos menores ocasionalmente "esquecem" de chamar `responder_usuario`. Uma alternativa mais robusta seria um nó final no grafo que força uma chamada com `with_structured_output(Resposta)` sobre o histórico de mensagens, eliminando a dependência do modelo "decidir" usar a tool certa.
- **Validação do JSON de gráficos/tabelas**: adicionar uma etapa de validação (ex: `jsonschema` para Vega-Lite) antes de enviar `chart`/`table` para a interface, com correção automática de erros comuns (ex: `values` fora de `data`).
- **Histórico de tool calls e queries por mensagem**: hoje `last_sql_queries` guarda apenas a última requisição; armazenar as queries por mensagem permitiria exibir o histórico completo de SQL no PDF exportado.

### Banco de dados

- **Suporte a múltiplos bancos / outros SGBDs**: abstrair `database.py` com SQLAlchemy permitiria trocar SQLite por Postgres/MySQL sem alterar `agent.py`.
- **Limites de segurança adicionais**: além de validar `SELECT`, considerar um limite de linhas (`LIMIT`) automático para evitar respostas excessivamente grandes, e bloquear acesso a tabelas sensíveis via lista de permissões.
- **Cache de schema**: `get_schema()` é chamado a cada interação; para bancos grandes, cachear o schema (invalidado apenas quando o banco mudar) reduziria latência.

### Interface

- **Histórico persistente**: salvar conversas em disco/banco para que o usuário possa retomar sessões anteriores após recarregar a página.
- **Múltiplos gráficos/tabelas por resposta**: hoje cada resposta suporta um gráfico OU uma tabela; permitir listas (`charts: list[str]`, `tables: list[str]`) possibilitaria respostas mais ricas.
- **Edição/refinamento de gráficos**: permitir que o usuário peça ajustes ("troque para gráfico de barras", "use cores diferentes") reaproveitando os dados já consultados, sem nova ida ao banco.
- **Exportação em outros formatos**: além de PDF, oferecer exportação em Excel/CSV dos dados das tabelas e gráficos.

### Observabilidade

- **Logging estruturado**: substituir os `print()` de depuração por um logger configurável, com níveis (debug/info/error) e, opcionalmente, integração com ferramentas de tracing de agentes (ex: LangSmith).
- **Métricas de uso**: número de queries executadas, taxa de erros de SQL, tempo médio de resposta — úteis para monitorar custo e qualidade do agente em produção.

### Modelo

- **Fallback entre modelos**: caso `gemini-3.1-flash-lite` falhe ou não chame as tools corretamente, tentar novamente com um modelo maior (ex: `gemini-3.1-pro`) antes de desistir.
- **Few-shot examples no prompt principal**: incluir exemplos de pares pergunta → SQL → resposta estruturada no `system_prompt` para melhorar a consistência do agente em consultas mais complexas (joins, agregações aninhadas, etc.).

---

## Estrutura do projeto

```
.
├── agent.py            # Definição do agente, tools e lógica de orquestração
├── app.py               # Interface Streamlit (chat, gráficos, tabelas, PDF)
├── database.py          # Acesso ao SQLite (schema + execução de SELECTs)
├── vega_skill.txt        # Exemplos e regras de sintaxe Vega-Lite
├── anexo_desafio_1.db    # Banco de dados SQLite (dados do usuário)
├── requirements.txt      # Dependências do projeto
└── .env                  # Variáveis de ambiente (GOOGLE_API_KEY) — não versionado
```
