import sqlite3

DB = 'anexo_desafio_1.db'

def run_sql_query(sql: str) -> tuple[bool, list[dict] | str]:
    """Executa uma consulta SQL arbitrária (somente SELECT) no banco do usuário."""
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT"):
        return False, "Apenas consultas SELECT são permitidas."
    try:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return True, rows
    except Exception as e:
        return False, f"Erro na consulta SQL: {str(e)}"


def get_schema() -> str:
    """Retorna o schema do banco do usuário para o LLM usar."""
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        schema_info = []
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            schema_info.append(f"Tabela: {table_name}")
            schema_info.append("Colunas:")
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                schema_info.append(f"  - {col_name} ({col_type})")
            schema_info.append("")
        
        conn.close()
        return "\n".join(schema_info)
    except Exception as e:
        return f"Erro ao recuperar schema: {str(e)}"
    
if __name__ == "__main__":
    print(get_schema())