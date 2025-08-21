import os
import sqlite3


def main():
    db_path = os.path.join(os.path.dirname(__file__), "db.sqlite3")
    out_path = os.path.join(os.path.dirname(__file__), "full_database.sql")

    if not os.path.exists(db_path):
        raise SystemExit(f"Base de données introuvable: {db_path}")

    con = sqlite3.connect(db_path)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            for line in con.iterdump():
                f.write(f"{line}\n")
        print(f"Dump SQL généré: {out_path}")
    finally:
        con.close()


if __name__ == "__main__":
    main()


