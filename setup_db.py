import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

columns = ["location", "visit_date", "category", "recommend"]
for col in columns:
    try:
        cur.execute(f"ALTER TABLE feedback ADD COLUMN {col} TEXT;")
    except:
        pass

conn.commit()
conn.close()
print("Database updated successfully!")
