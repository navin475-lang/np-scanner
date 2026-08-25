import sqlite3

conn = sqlite3.connect("fundatech.db")
cursor = conn.cursor()

while True:

    sql = input("SQL> ")

    if sql.lower() in ["quit", "exit"]:
        break

    try:
        rows = cursor.execute(sql).fetchall()

        for row in rows:
            print(row)

    except Exception as e:
        print(e)

conn.close()