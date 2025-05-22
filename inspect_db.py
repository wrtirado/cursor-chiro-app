import asyncio
import libsql_client
import os
from dotenv import load_dotenv

def get_adapted_db_url():
    dotenv_path = "/app/.env"
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        # print(f"Loaded .env file from {dotenv_path}") # Less verbose
    else:
        print(f"Warning: .env file not found at {dotenv_path}. DATABASE_URL must be set in environment.")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in environment or .env file.")
        return None

    # print(f"Original DATABASE_URL from env: {db_url}") # Less verbose
    adapted_url = db_url
    if db_url.startswith("sqlite+libsql://"):
        adapted_url = db_url.replace("sqlite+libsql://", "http://", 1)
        # print(f"Adapted URL to: {adapted_url}") # Less verbose
    elif db_url.startswith("sqlite+http://"):
        adapted_url = db_url.replace("sqlite+http://", "http://", 1)
        # print(f"Adapted URL to: {adapted_url}") # Less verbose
    elif db_url.startswith("sqlite+ws://"):
        adapted_url = db_url.replace("sqlite+ws://", "ws://", 1)
        # print(f"Adapted URL to: {adapted_url}") # Less verbose
    elif not (db_url.startswith("http://") or db_url.startswith("https://") or db_url.startswith("ws://") or db_url.startswith("wss://") or db_url.startswith("file:")):
        print(f"Warning: URL scheme for {db_url} might not be directly supported or adapted. Trying as is.")

    return adapted_url

async def run_query(sql_query, params=None):
    url = get_adapted_db_url()
    if not url:
        return

    # print(f"Attempting to connect to: {url}") # Less verbose
    try:
        async with libsql_client.create_client(url) as client:
            print(f"Executing SQL: {sql_query}")
            if params:
                print(f"With parameters: {params}")

            rs = await client.execute(sql_query, params)

            # Check if columns attribute exists and has content, and if rows exist
            if hasattr(rs, 'columns') and rs.columns and rs.rows:
                header = " | ".join(str(col) for col in rs.columns)
                print(header)
                print("-" * len(header))
                for row in rs.rows:
                    print(" | ".join(str(item) for item in row))
            # Check for results from DML like INSERT, UPDATE, DELETE
            elif hasattr(rs, 'rows_affected') and rs.rows_affected is not None:
                 print(f"Query executed successfully. Rows affected: {rs.rows_affected}. Last insert rowid: {rs.last_insert_rowid if hasattr(rs, 'last_insert_rowid') else 'N/A'}")
            # Check if columns attribute exists but no rows (e.g. PRAGMA table_info on non-existent table, or SELECT on empty table)
            elif hasattr(rs, 'columns') and rs.columns:
                header = " | ".join(str(col) for col in rs.columns)
                print(header)
                print("-" * len(header))
                print("(No rows returned for this query)")
            else:
                # Catch-all for other cases, like PRAGMA statements that don't fit above, or DDL.
                # Some PRAGMAs might return rows/columns, some might not have a clear structure.
                # If rs.rows exists and is empty, this might also be a path.
                if rs.rows is not None and not rs.rows and not (hasattr(rs, 'columns') and rs.columns): # Empty rows, no columns
                     print("Query executed successfully, no data returned (e.g., empty table or PRAGMA with no output).")
                elif rs.rows is None and not (hasattr(rs, 'columns') and rs.columns): # No rows attribute, no columns
                     print("Query executed, but the result structure is not standard for SELECT/PRAGMA table_info (possibly DDL or specific PRAGMA).")
                else: # Fallback for unhandled structures
                    print(f"Query executed. Result details: rows_affected={getattr(rs, 'rows_affected', 'N/A')}, last_insert_rowid={getattr(rs, 'last_insert_rowid', 'N/A')}, columns={getattr(rs, 'columns', 'N/A')}")


    except libsql_client.client.LibsqlError as e:
        print(f"LibsqlError: {e.message} (Code: {e.code})")
    except AttributeError as e_attr: # Catch specific AttributeError
        print(f"AttributeError: {e_attr}. This might indicate an unexpected structure in the ResultSet.")
        print(f"ResultSet attributes: {dir(rs) if 'rs' in locals() else 'rs not defined'}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if 'rs' in locals():
            print(f"ResultSet object: {rs}")
            print(f"ResultSet attributes: {dir(rs)}")


async def main():
    print("\n--- Listing All Tables ---")
    await run_query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_litestream_%' AND name NOT LIKE 'libsql_%';")

    print("\n--- Schema for Users Table ---")
    await run_query("PRAGMA table_info(Users);")

    print("\n--- Schema for migrations Table ---")
    await run_query("PRAGMA table_info(migrations);")

    print("\n--- Data from Roles Table ---")
    await run_query("SELECT * FROM Roles;")

    print("\n--- Data from migrations Table ---")
    await run_query("SELECT * FROM migrations;")

if __name__ == "__main__":
    asyncio.run(main())
