from pydantic_settings import BaseSettings
from typing import Optional

# pydantic_settings is not part of the core pydantic package anymore. Since Pydantic v2, the settings functionality has been split out into its own package.
# BaseSettings from pydantic-settings allow values to be pulled from the .env file (by its default), and provide defaults where applicable.


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Clerk webhook secret
    CLERK_WEBHOOK_SECRET: Optional[str] = None

    # Clerk JWT settings
    CLERK_JWKS_URL: str

    # API Settings
    API_V1_STR: str = "/api/v1"

    # Stripe settings
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # Resend API Key
    RESEND_API_KEY: str

    # domains
    CLIENT_DOMAIN: str

    class Config:
        # You can explicitly tell Pydantic which file to target -> So you are not forced to use a specific name; you just tell Pydantic which one.
        # here, Pydantic (via python-dotenv) will try to open “.env” relative to the CWD of python running process.
        # this means where (path directory) is the terminal when you run `python main.py` or `uvicorn main:app --reload`

        # When running locally:
        # 1. System environment variables are checked first
        # 2. If a variable isn't found in the system environment, BaseSettings will load it from your .env file (we will always have .env file locally)
        # 3. Automatic loading - No need to explicitly call load_dotenv() or import python-dotenv in your code, as pydantic-settings handles that for you.

        # when in production
        # 1. there is no .env file, but environment variables are set in the deployment environment manager (e.g. render dashboard).
        # 2. BaseSettings will only retrieve values from the system environment variables
        # 3. Graceful handling - If the .env file doesn't exist, Pydantic won't throw an error - it just won't load anything from it

        # priority handling, the order is:
        # 1. System environment variables (highest priority)
        # 2. .env file (if it exists)
        # 3. Default values in the Settings class (lowest priority)

        env_file = ".env"  # Pydantic will try to load this file (using python-dotenv under the hood) and read variables from it.
        case_sensitive = True


# A module is a .py file; executing `import module` runs all top-level code once.
# Python compiles and executes the module, initializing its namespace
# Imported modules are cached in sys.modules.
# Subsequent imports within the same interpreter reuse this cached module -> no re-execution (very important)
# If you import the same module in a different script/process, top-level code runs again (new session’s cache is empty)

# throughout your entire project, no matter how many files do "from config import settings"
# that module (and Settings() initialization) only runs once per python execution process. Everything else uses the cached module and settings instance.
settings = Settings()
