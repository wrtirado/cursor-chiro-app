from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # Import CORS Middleware
# Import other routers as they are created
from api.core.config import settings
from api.auth.router import router as auth_router
from api.users.router import router as users_router # Import users router
from api.companies.router import router as companies_router # Import companies router
from api.offices.router import router as offices_router # Import offices router
from api.plans.router import router as plans_router # Import plans router
from api.media.router import router as media_router # Import media router
from api.progress.router import router as progress_router # Import progress router
# from api.routers import plans # etc.

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for the Tirado Chiropractic mobile and web applications.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS Middleware
origins = [
    "http://localhost:3000", # Allow the React frontend development server
    "http://localhost:5173", # Allow Vite default dev port just in case
    # Add other origins if needed (e.g., deployed frontend URL)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # List of allowed origins
    allow_credentials=True, # Allow cookies/auth headers
    allow_methods=["*"],    # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],    # Allow all headers
)

@app.get("/")
def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}

# Include routers
app.include_router(auth_router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(users_router, prefix=settings.API_V1_STR + "/users", tags=["users"]) # Add users router
app.include_router(companies_router, prefix=settings.API_V1_STR + "/companies", tags=["companies"])
app.include_router(offices_router, prefix=settings.API_V1_STR + "/offices", tags=["offices"])
app.include_router(plans_router, prefix=settings.API_V1_STR + "/plans", tags=["plans"]) # Add plans router
app.include_router(media_router, prefix=settings.API_V1_STR + "/media", tags=["media"]) # Add media router
app.include_router(progress_router, prefix=settings.API_V1_STR + "/progress", tags=["progress"]) # Add progress router

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