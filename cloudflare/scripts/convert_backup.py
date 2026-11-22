"""Validate offline CSV exports and generate a D1 import without querying a database."""

import argparse
import csv
import os
import re
import sqlite3
from pathlib import Path


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def identifier(value):
    return '"' + str(value).replace('"', '""') + '"'


def numeric_id(row, key):
    value = row[key]
    if not value.isdecimal() or not value.isascii():
        raise ValueError(f"Invalid numeric ID in column {key}")
    return value


def product_id(row, key):
    value = row[key]
    # One historical crawler record contains a trailing /add command.
    # Preserve its primary/foreign keys exactly; the fetcher resolves the numeric ID.
    if not re.fullmatch(r"[0-9]+(?:\s+/add)?", value):
        raise ValueError(f"Invalid product ID in column {key}")
    return value


def integer(row, key, allowed=None, default=None):
    raw = row.get(key)
    if raw in (None, "", "NULL", "\\N"):
        if default is None:
            raise ValueError(f"Missing value for {key}")
        value = default
    elif raw.lower() in ("true", "t"):
        value = 1
    elif raw.lower() in ("false", "f"):
        value = 0
    else:
        value = int(raw)
    if allowed is not None and value not in allowed:
        raise ValueError(f"Invalid {key}")
    return value


def convert(source):
    statements = []
    counts = {}

    def add(table, columns, values):
        names = ", ".join(identifier(column) for column in columns)
        statements.append(
            f'INSERT INTO {identifier(table)} ({names}) VALUES ({", ".join(map(literal, values))});'
        )

    for table in ("user", "good_info", "user_sub_good"):
        with (source / f"{table}.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        counts[table] = len(rows)
        for index, row in enumerate(rows):
            times = [
                row.get(key) or "1970-01-01 00:00:00" for key in ("create_time", "update_time")
            ]
            state = integer(row, "state", (0, 1), default=1)
            if table == "user":
                add(
                    table,
                    ["id", "chat_id", "state", "create_time", "update_time"],
                    [numeric_id(row, "id"), numeric_id(row, "chat_id"), state, *times],
                )
            elif table == "good_info":
                add(
                    table,
                    [
                        "id",
                        "name",
                        "price",
                        "stock_state",
                        "state",
                        "next_check",
                        "create_time",
                        "update_time",
                    ],
                    [
                        product_id(row, "id"),
                        row["name"][:500],
                        integer(row, "price"),
                        integer(row, "stock_state", (0, 1, 2), default=1),
                        state,
                        index % 240 * 60,
                        *times,
                    ],
                )
            else:
                add(
                    table,
                    [
                        "id",
                        "user_id",
                        "good_id",
                        "price",
                        "is_notified",
                        "state",
                        "create_time",
                        "update_time",
                    ],
                    [
                        row["id"],
                        numeric_id(row, "user_id"),
                        product_id(row, "good_id"),
                        integer(row, "price"),
                        integer(row, "is_notified", (0, 1), default=0),
                        state,
                        *times,
                    ],
                )

    sql = "\n".join(statements) + "\n"
    # An isolated SQLite database verifies every constraint and relationship before output.
    with sqlite3.connect(":memory:") as database:
        schema = Path(__file__).resolve().parents[1] / "migrations" / "0001_initial.sql"
        database.executescript(schema.read_text())
        database.executescript(sql)
        if database.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Backup has missing parent rows")
        for table, count in counts.items():
            if database.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] != count:
                raise ValueError(f"Row count mismatch for {table}")
    return sql, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="Directory with user.csv, good_info.csv, user_sub_good.csv"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sql, counts = convert(args.source)
    # Fail if the output exists; never replace the user's previous migration artifact.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(sql)
    print(f"Validated rows: {counts}. Wrote private import file: {args.output}")


if __name__ == "__main__":
    main()
