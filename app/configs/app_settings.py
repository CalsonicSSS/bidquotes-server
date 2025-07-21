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

    class Config:
        env_file = ".env"
        case_sensitive = True


# A module is a .py file; executing `import module` runs all top-level code once.
# Python compiles and executes the module, initializing its namespace
# Imported modules are cached in sys.modules.
# Subsequent imports within the same interpreter reuse this cached module -> no re-execution (very important)
# If you import the same module in a different script/process, top-level code runs again (new session’s cache is empty)

# throughout your entire project, no matter how many files do "from config import settings"
# that module (and Settings() initialization) only runs once per python execution process. Everything else uses the cached module and settings instance.
settings = Settings()
