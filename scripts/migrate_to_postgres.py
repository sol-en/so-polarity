#!/usr/bin/env python3
"""
Скрипт перенесення всіх даних із SQLite (zhbk_app.db) у PostgreSQL (Render/Neon).
"""

import os
import sys
import argparse
from sqlalchemy import create_engine, select, text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import Base
from backend import models, bank_models  # реєстрація всіх моделей


def migrate(sqlite_path: str, target_db_url: str):
    if target_db_url.startswith("postgres://"):
        target_db_url = target_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif target_db_url.startswith("postgresql://") and not target_db_url.startswith("postgresql+"):
        target_db_url = target_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    print(f"📦 Джерело SQLite: {sqlite_path}")
    print(f"🚀 Цільова БД PostgreSQL: {target_db_url.split('@')[-1] if '@' in target_db_url else 'target'}")

    src_engine = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})
    dst_engine = create_engine(target_db_url, pool_pre_ping=True)

    print("\n🛠️ Створення структури таблиць у PostgreSQL...")
    Base.metadata.create_all(bind=dst_engine)

    total_migrated = 0
    is_postgres = "postgres" in target_db_url.lower()

    with dst_engine.connect() as dst_conn:
        print("\n🧹 Очищення старих даних у зворотньому порядку залежностей...")
        for table in reversed(Base.metadata.sorted_tables):
            try:
                dst_conn.execute(table.delete())
                dst_conn.commit()
            except Exception as e:
                dst_conn.rollback()

    with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
        print("\n📥 Копіювання таблиць у порядку зв'язків...")
        for table in Base.metadata.sorted_tables:
            table_name = table.name
            try:
                rows = src_conn.execute(select(table)).mappings().all()
                if not rows:
                    continue

                data_to_insert = [dict(r) for r in rows]
                dst_conn.execute(table.insert(), data_to_insert)
                dst_conn.commit()

                print(f"  ✅ {table_name}: скопійовано {len(data_to_insert)} рядків")
                total_migrated += len(data_to_insert)

                # Оновлюємо послідовність автоінкременту (id sequence)
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
                dst_conn.rollback()
                print(f"  ❌ Помилка при копіюванні таблиці {table_name}: {e}")

    print(f"\n🎉 Міграцію завершено! Загалом перенесено {total_migrated} записів.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Міграція даних ЖБК з SQLite у PostgreSQL")
    parser.add_argument("--source", default="./zhbk_app.db", help="Шлях до файлу SQLite бази")
    parser.add_argument("--target", default=os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL"),
                        help="Connection string до PostgreSQL")

    args = parser.parse_args()

    if not args.target:
        print("❌ Помилка: Не вказано цільову базу даних.")
        sys.exit(1)

    migrate(args.source, args.target)
