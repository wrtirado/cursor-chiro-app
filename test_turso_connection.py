import os
import logging
import libsql_client

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

auth_token = os.environ.get("LIBSQL_AUTH_TOKEN")
if not auth_token:
    print("Error: LIBSQL_AUTH_TOKEN environment variable not set.")
    exit(1)

turso_db_hostname = "chiro-app-wrtirado.aws-us-west-2.turso.io"
client_url = f"wss://{turso_db_hostname}?authToken={auth_token}"

print(f"Attempting to connect to: {client_url}")
try:
    client = libsql_client.create_client_sync(url=client_url)
    print("Client created successfully.")
    rs = client.execute("SELECT 1")
    print(f"Query result: {rs.rows}")
finally:
    if "client" in locals():
        client.close()
        print("Client closed.")

# # test_turso_connection.py
# import os
# import libsql_client

# # Ensure LIBSQL_AUTH_TOKEN is available as an environment variable
# auth_token = os.environ.get("LIBSQL_AUTH_TOKEN")

# if not auth_token:
#     print("Error: LIBSQL_AUTH_TOKEN environment variable not set.")
#     exit(1)

# # Using the libsql scheme directly as Turso provides, with authToken in the URL query
# # The sqlalchemy-libsql dialect would normally handle the sqlite+libsql part.
# # Here we test the underlying client with what it typically expects for a remote server.
# turso_db_hostname = "chiro-app-wrtirado.aws-us-west-2.turso.io"
# # client_url = f"libsql://{turso_db_hostname}?authToken={auth_token}"
# client_url = f"wss://{turso_db_hostname}?authToken={auth_token}"

# print(
#     f"Attempting to connect to: {client_url} (using libsql_client.create_client_sync)"
# )

# try:
#     # create_client_sync is used because SQLAlchemy operates synchronously
#     # and its DBAPI drivers are expected to be synchronous.
#     client = libsql_client.create_client_sync(url=client_url)
#     print("Client created successfully.")

#     # Test with a simple query to ensure the connection is usable
#     print("Attempting to execute a simple query (SELECT 1)...")
#     rs = client.execute("SELECT 1")

#     print(
#         f"Query executed successfully. Result rows: {rs.rows}, Column names: {rs.columns}"
#     )

#     if rs.rows and len(rs.rows) > 0 and rs.rows[0][0] == 1:
#         print("Connection and basic query successful!")
#     else:
#         print(
#             "Query executed, but result was not as expected (expected [[1]] or similar)."
#         )

# except Exception as e:
#     print(f"Connection or query failed: {e}")
#     print(f"Type of exception: {type(e)}")
#     if hasattr(e, "args"):
#         print(f"Exception args: {e.args}")
#     # If there are nested exceptions, like in the Alembic traceback
#     if e.__cause__:
#         print(f"Cause: {e.__cause__}")
#         print(f"Type of cause: {type(e.__cause__)}")
#     if e.__context__:
#         print(f"Context: {e.__context__}")
#         print(f"Type of context: {type(e.__context__)}")


# finally:
#     if "client" in locals() and client:
#         client.close()
#         print("Client closed.")
