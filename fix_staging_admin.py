"""Fix staging admin user: create in users table with correct supabase_id."""
import os
import uuid
import psycopg

service_key = os.environ["SERVICE_KEY"]
db_host = os.environ["DB_HOST"]

conn = psycopg.connect(
    host=db_host,
    port=5432,
    user="postgres",
    password=service_key,
    dbname="postgres",
    connect_timeout=5,
)
cur = conn.cursor()

# Check existing users with this email
cur.execute("SELECT user_id, email, user_role, supabase_id FROM users WHERE email = 'apineorbeenga@gmail.com'")
row = cur.fetchone()
if row:
    print(f"Found existing user: id={row[0]}, role={row[2]}, supabase_id={row[3]}")
    if row[3]:
        print("User already has supabase_id. Try logging in via auth.")
    else:
        # Update with new supabase_id
        new_id = str(uuid.uuid4())
        cur.execute("UPDATE users SET supabase_id = %s WHERE user_id = %s", (new_id, row[0]))
        conn.commit()
        print(f"Updated supabase_id to {new_id}")
else:
    print("User not found in database")
    
    # Check what users exist
    cur.execute("SELECT user_id, email, user_role FROM users ORDER BY user_id LIMIT 10")
    all_users = cur.fetchall()
    print("Existing users:")
    for u in all_users:
        print(f"  {u[0]}: {u[1]} ({u[2]})")

cur.close()
conn.close()
