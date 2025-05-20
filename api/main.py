from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Import CORS Middleware

# Import exception handlers
from fastapi.exceptions import HTTPException
from api.core.exceptions import generic_exception_handler, http_exception_handler

# Import other routers as they are created
from api.core.config import settings
from api.core.middleware import SecureHeadersMiddleware  # Import the new middleware
from api.auth.router import router as auth_router
from api.users.router import router as users_router  # Import users router
from api.companies.router import router as companies_router  # Import companies router
from api.offices.router import router as offices_router  # Import offices router
from api.plans.router import router as plans_router  # Import plans router
from api.media.router import router as media_router  # Import media router
from api.progress.router import router as progress_router  # Import progress router

# --- Temporary for DB connection testing: Create tables ---
from api.database.session import engine, Base  # ADD THIS LINE
import api.models.base
import traceback  # Add this import for more detailed error printing

# WARNING: This is for initial setup/testing ...
print("Attempting to create database tables directly for test...")
engine_conn_attempted = False
try:
    print(f"Using DATABASE_URL: {settings.DATABASE_URL}")  # Print the URL being used
    print(f"Engine object: {engine}")
    engine_conn_attempted = True  # Mark that we are about to try connecting

    # Attempt a very basic connection first
    print("Attempting a direct engine connection test...")
    with engine.connect() as connection:
        print("Engine.connect() was successful. Connection established.")
        # Optionally, execute a simple query
        # result = connection.execute(text("SELECT 1"))
        # print(f"Direct engine query result: {result.scalar_one_or_none()}")
    print("Direct engine connection test passed.")

    print("Now attempting Base.metadata.create_all(bind=engine)...")
    Base.metadata.create_all(bind=engine)
    print("Base.metadata.create_all(bind=engine) executed successfully.")
except Exception as e:
    print("--------------------------------------------------------------------")
    print(
        f"!!! ERROR during database initialization (engine_conn_attempted: {engine_conn_attempted}) !!!"
    )
    print(f"Error type: {type(e)}")
    print(f"Error message: {e}")
    print("Full traceback:")
    traceback.print_exc()  # This will print the full stack trace
    print("--------------------------------------------------------------------")
    # Depending on how critical this is for startup, you might want to:
    # import sys
    # sys.exit(f"FATAL: Could not create database tables: {e}")
# --- End Temporary DB connection testing ---

# from api.routers import plans # etc.

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for the Tirado Chiropractic mobile and web applications.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # Register exception handlers
    exception_handlers={
        Exception: generic_exception_handler,
        HTTPException: http_exception_handler,
        # Add other handlers here if needed, e.g.:
        # RequestValidationError: validation_exception_handler
    },
)

# Set up CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Use origins from settings
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Add the Secure Headers Middleware
app.add_middleware(SecureHeadersMiddleware)


@app.get("/")
def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}


# Include routers
app.include_router(auth_router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(
    users_router, prefix=settings.API_V1_STR + "/users", tags=["users"]
)  # Add users router
app.include_router(
    companies_router, prefix=settings.API_V1_STR + "/companies", tags=["companies"]
)
app.include_router(
    offices_router, prefix=settings.API_V1_STR + "/offices", tags=["offices"]
)
app.include_router(
    plans_router, prefix=settings.API_V1_STR + "/plans", tags=["plans"]
)  # Add plans router
app.include_router(
    media_router, prefix=settings.API_V1_STR + "/media", tags=["media"]
)  # Add media router
app.include_router(
    progress_router, prefix=settings.API_V1_STR + "/progress", tags=["progress"]
)  # Add progress router

# Add middleware (e.g., CORS) if needed later
# from fastapi.middleware.cors import CORSMiddleware
# origins = [ "*" ] # Configure appropriately for production
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
