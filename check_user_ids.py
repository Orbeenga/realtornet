import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
    result = conn.execute(
        text("SELECT user_id, email, user_role, supabase_id, is_verified FROM users WHERE email IN ('apineorbeenga@yahoo.com','apineorbeenga@outlook.com','apineterngu19@gmail.com')")
    )
    for row in result:
        print(f"id={row[0]} email={row[1]} role={row[2]} supabase_id={row[3]} verified={row[4]}")
