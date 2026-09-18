import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "backend" / ".env")

try:
    import mysql.connector

    required = {
        "MYSQL_HOST": os.environ.get("MYSQL_HOST"),
        "MYSQL_PORT": os.environ.get("MYSQL_PORT"),
        "MYSQL_DATABASE": os.environ.get("MYSQL_DATABASE"),
        "MYSQL_USER": os.environ.get("MYSQL_USER"),
        "MYSQL_PASSWORD": os.environ.get("MYSQL_PASSWORD"),
    }
    placeholder = {key: value for key, value in required.items() if value is None or str(value).strip() == "<REPLACE_ME>"}
    if placeholder:
        raise ValueError(f"Placeholder MySQL config detected: {placeholder}")

    connection = mysql.connector.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
    )
    cursor = connection.cursor()
    cursor.execute("SELECT DATABASE();")
    db_name = cursor.fetchone()[0]
    print(f"Connected to MySQL database: {db_name}")
    cursor.close()
    connection.close()
    print("[PASS] MySQL connection OK")
except Exception as exc:
    print(f"[FAIL] MySQL connection failed: {exc}")
