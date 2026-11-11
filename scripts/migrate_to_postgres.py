#!/usr/bin/env python3
"""
Скрипт перенесення всіх даних із SQLite (zhbk_app.db) у PostgreSQL (Render/Neon).
Використання:
    python3 scripts/migrate_to_postgres.py --target "postgresql://user:pass@host:5432/dbname"
або задати змінну оточення TARGET_DATABASE_URL:
    export TARGET_DATABASE_URL="postgresql://..."
    python3 scripts/migrate_to_postgres.py
"""

import os
import sys
import argparse
from sqlalchemy import create_engine, select, text

# Додаємо кореневу папку в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import Base
from backend import models, bank_models  # реєстрація всіх моделей


def migrate(sqlite_path: str, target_db_url: str):
    if target_db_url.startswith("postgres://"):
        target_db_url = target_db_url.replace("postgres://", "postgresql://", 1)

    print(f"📦 Джерело SQLite: {sqlite_path}")
    print(f"🚀 Цільова БД PostgreSQL: {target_db_url.split('@')[-1] if '@' in target_db_url else 'target'}")

    src_engine = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})
    dst_engine = create_engine(target_db_url, pool_pre_ping=True)

    print("\n🛠️ Створення структури таблиць у PostgreSQL...")
    Base.metadata.create_all(bind=dst_engine)

    total_migrated = 0

    with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
        is_postgres = "postgres" in target_db_url.lower()
        if is_postgres:
            try:
                dst_conn.execute(text("SET session_replication_role = 'replica';"))
            except Exception as e:
                print(f"Попередження щодо session_replication_role: {e}")

        for table in Base.metadata.sorted_tables:
            table_name = table.name
            try:
                rows = src_conn.execute(select(table)).mappings().all()
                if not rows:
                    continue

                # Очистити таблицю призначення перед записом
                dst_conn.execute(table.delete())

                # Вставити пакетами
                data_to_insert = [dict(r) for r in rows]
                dst_conn.execute(table.insert(), data_to_insert)
                dst_conn.commit()

                print(f"  ✅ {table_name}: скопійовано {len(data_to_insert)} рядків")
                total_migrated += len(data_to_insert)

                # Оновити автоінкремент (SEQUENCE) у Postgres
                if is_postgres:
                    try:
                        dst_conn.execute(text(f"""
                            SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), 
                                          COALESCE(MAX(id), 1), 
                                          MAX(id) IS NOT NULL) 
                            FROM "{table_name}";
                        """))
                        dst_conn.commit()
                    except Exception:
                        pass
            except Exception as e:
                print(f"  ❌ Помилка при копіюванні таблиці {table_name}: {e}")

        if is_postgres:
            try:
                dst_conn.execute(text("SET session_replication_role = 'origin';"))
                dst_conn.commit()
            except Exception:
                pass

    print(f"\n🎉 Міграцію завершено! Загалом перенесено {total_migrated} записів.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Міграція даних ЖБК з SQLite у PostgreSQL")
    parser.add_argument("--source", default="./zhbk_app.db", help="Шлях до файлу SQLite бази")
    parser.add_argument("--target", default=os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL"),
                        help="Connection string до PostgreSQL")

    args = parser.parse_args()

    if not args.target:
        print("❌ Помилка: Не вказано цільову базу даних.")
        print("Вкажіть через аргумент: --target \"postgresql://user:pass@host:5432/dbname\"")
        print("Або експортуйте змінну оточення TARGET_DATABASE_URL.")
        sys.exit(1)

    migrate(args.source, args.target)
