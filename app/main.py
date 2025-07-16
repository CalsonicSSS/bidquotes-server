from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bidquotes API",
    version="1.0.0",
)

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


@app.get("/")
async def root():
    return {"message": "Welcome to Bidquotes API"}
