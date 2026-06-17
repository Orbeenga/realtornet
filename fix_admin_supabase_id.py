"""Fix admin supabase_id to match new auth user."""
import os
from sqlalchemy import create_engine, text

db_url = os.environ["DB_URL"]
new_sid = os.environ["NEW_SID"]

engine = create_engine(db_url)
with engine.connect() as conn:
    conn.execute(
        text("UPDATE users SET supabase_id = :sid, is_verified = true WHERE email = 'apineorbeenga@gmail.com'"),
        {"sid": new_sid}
    )
    conn.commit()
    result = conn.execute(
        text("SELECT user_id, email, user_role, supabase_id, is_verified FROM users WHERE email = 'apineorbeenga@gmail.com'")
    )
    row = result.fetchone()
    print(f"user_id={row[0]} email={row[1]} role={row[2]} supabase_id={row[3]} verified={row[4]}")
