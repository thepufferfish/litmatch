import psycopg2
from pathlib import Path

def init():
    sql = Path("db/schema.sql").read_text()
    conn = psycopg2.connect(
        dbname="bookdb", user="bookuser", password="bookpass", host="localhost"
    )
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init()
