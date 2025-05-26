import libsql_client


def check_schema():
    client = libsql_client.create_client_sync(url="http://localhost:8080")

    # Check invoice table schema
    result = client.execute("PRAGMA table_info(invoice);")
    print("Invoice table schema:")
    for row in result.rows:
        nullable = "nullable" if not row[3] else "NOT NULL"
        default = f"default: {row[4]}" if row[4] else "no default"
        pk = "PRIMARY KEY" if row[5] else ""
        print(f"  {row[1]} {row[2]} ({nullable}, {default}) {pk}")

    client.close()


if __name__ == "__main__":
    check_schema()
