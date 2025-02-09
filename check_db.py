import sqlite3

# Conecta ao banco de dados inventario.db
conn = sqlite3.connect('inventario.db')
cursor = conn.cursor()

# Executa uma consulta para listar todas as tabelas do banco de dados
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tabelas = cursor.fetchall()

print("Tabelas encontradas no banco de dados:")
for tabela in tabelas:
    print(tabela[0])

conn.close()
