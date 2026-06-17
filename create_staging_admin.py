"""Create admin user in staging Supabase database."""
import os
import uuid
from sqlalchemy import create_engine, text

db_url = os.environ["DB_URL"]
new_supabase_id = str(uuid.uuid4())

engine = create_engine(db_url)
with engine.connect() as conn:
    # Check if user exists
    result = conn.execute(
        text("SELECT user_id, user_role, supabase_id FROM users WHERE email = 'apineorbeenga@gmail.com'")
    )
    row = result.fetchone()
    if row:
        print(f"User exists: id={row[0]}, role={row[1]}, supabase_id={row[2]}")
        if row[2] is None:
            conn.execute(
                text("UPDATE users SET supabase_id = :sid WHERE user_id = :uid"),
                {"sid": new_supabase_id, "uid": row[0]}
            )
            conn.commit()
            print(f"Updated supabase_id to {new_supabase_id}")
        else:
            print("supabase_id already set, attempting to use existing auth user...")
    else:
        print("User not found. Creating...")
        conn.execute(
            text("""
                INSERT INTO users (supabase_id, email, first_name, last_name, user_role, is_verified)
                VALUES (:sid, 'apineorbeenga@gmail.com', 'Orbeenga', 'Apine', 'admin', true)
            """),
            {"sid": new_supabase_id}
        )
        conn.commit()
        print(f"Created admin user with supabase_id={new_supabase_id}")

    # Verify
    result = conn.execute(
        text("SELECT user_id, email, user_role, supabase_id, is_verified FROM users WHERE email = 'apineorbeenga@gmail.com'")
    )
    row = result.fetchone()
    if row:
        print(f"Verified: id={row[0]}, email={row[1]}, role={row[2]}, supabase_id={row[3]}, verified={row[4]}")
