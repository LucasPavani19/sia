import sqlite3

conn = sqlite3.connect('inventario.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tabelas = cursor.fetchall()

print("Tabelas encontradas no banco de dados:")
for tabela in tabelas:
    print(tabela[0])

conn.close()
