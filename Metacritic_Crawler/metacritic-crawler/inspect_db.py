"""Xem database bằng Python; không cần cài phần mềm SQLite."""
import argparse
import sqlite3
import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Đường dẫn crawler.db; mặc định là lần chạy mới nhất")
    args = parser.parse_args()
    candidates = sorted(config.DATA_DIR.glob("run_*/crawler.db"))
    if not args.db and not candidates:
        parser.error("Chưa có database. Chạy python main.py trước.")
    path = args.db or candidates[-1]
    with sqlite3.connect(path) as db:
        print("Database:", path)
        for table in ("pages", "links", "events"):
            print(table, db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for row in db.execute("SELECT id, depth, domain, title FROM pages LIMIT 10"):
            print(row)
        print("\nPages by domain:")
        for row in db.execute("SELECT domain, COUNT(*) FROM pages GROUP BY domain"):
            print(row)


if __name__ == "__main__":
    main()

