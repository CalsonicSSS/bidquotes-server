from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.utils.supabase_client_handlers import create_supabase_client, close_supabase_client
from app.routes.user_routes import user_router
from app.routes.clerk_webhook_routes import clerk_webhook_router
from app.configs.app_settings import settings
from app.routes.job_routes import job_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # before yield = code to run during startup
    await create_supabase_client()
    print("✅ Supabase async client initialized")

    yield
    # after yield = code to run during shutdown
    await close_supabase_client()
    print("✅ Supabase client closed")


app = FastAPI(title="Bidquotes API", version="1.0.0", lifespan=lifespan)

# Add CORS middleware
# all 4 arugments are specific to the CORS middleware only, not generic within the add_middleware function
# CORSMiddleware is one of the official premade middleware classes included in Starlette, which FastAPI is built on top of.
# there are some other premade middleware classes in Starlette, such as GZipMiddleware, TrustedHostMiddleware, and SessionMiddleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(user_router, prefix=settings.API_V1_STR)
app.include_router(clerk_webhook_router, prefix=settings.API_V1_STR)
app.include_router(job_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "Welcome to Bidquotes API"}
