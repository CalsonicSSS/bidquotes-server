from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.utils.supabase_client_handlers import create_supabase_client, close_supabase_client
from app.routes.user_routes import user_router
from app.routes.clerk_webhook_routes import clerk_webhook_router
from app.configs.app_settings import settings
from app.routes.buyer_jobs_routes import buyer_job_router
from app.routes.contractor_jobs_routes import contractor_jobs_router
from app.routes.contractor_profile_routes import contractor_profile_router
from app.routes.contractor_bid_routes import bid_router


from fastapi.exceptions import RequestValidationError
from app.custom_error import EmailValidationError


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


# Global Exception Handler for Pydantic ValidationError (put in your main.py file, after creating the FastAPI() instance.)
# will apply across your entire FastAPI application, catching validation errors from: Request body (like your EmailStr), Query parameters, Path params, etc.
# This only runs when there is any request Validation error only happens
@app.exception_handler(RequestValidationError)
async def custom_request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    print("custom_request_validation_exception_handler runs")

    for error in exc.errors():
        loc = error.get("loc", [])
        field = loc[-1] if loc else None

        if field == "contact_email":
            raise EmailValidationError()

    # Return a proper JSON response for other validation errors
    return JSONResponse(status_code=400, content={"detail": "Validation error", "errors": exc.errors()})


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
app.include_router(buyer_job_router, prefix=settings.API_V1_STR)
app.include_router(contractor_profile_router, prefix=settings.API_V1_STR)
app.include_router(contractor_jobs_router, prefix=settings.API_V1_STR)
app.include_router(bid_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "Welcome to Bidquotes API"}
