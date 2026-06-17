import psycopg2
import os

service_key = os.environ["SERVICE_KEY"]
db_host = os.environ["DB_HOST"]

try:
    conn = psycopg2.connect(
        host=db_host,
        port=5432,
        user="postgres",
        password=service_key,
        dbname="postgres",
        connect_timeout=5,
    )
    cur = conn.cursor()
    cur.execute("SELECT email, user_role FROM users WHERE email LIKE 'apineorbeenga%' ORDER BY email")
    for row in cur.fetchall():
        print(f"user: {row[0]} role: {row[1]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"DB error: {e}")
