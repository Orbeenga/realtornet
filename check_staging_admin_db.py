import psycopg2
conn = psycopg2.connect("postgresql+psycopg://postgres.avkhpachzsbgmbnkfnhu:REDACTED@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require")
cur = conn.cursor()
cur.execute("SELECT user_id, email, user_role, supabase_id::text, agency_id FROM users WHERE email = 'apineorbeenga@gmail.com'")
row = cur.fetchone()
print(row)
cur.close()
conn.close()
