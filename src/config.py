import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Settings
    MOCK_MODE: bool = True
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/warehouse"

    # Stripe Credentials
    STRIPE_API_KEY: str = "mock_stripe_key"

    # Salesforce Credentials
    SALESFORCE_USERNAME: str = "mock_sf_username"
    SALESFORCE_PASSWORD: str = "mock_sf_password"
    SALESFORCE_SECURITY_TOKEN: str = "mock_sf_token"
    SALESFORCE_CLIENT_ID: str = "mock_sf_client_id"
    SALESFORCE_CLIENT_SECRET: str = "mock_sf_client_secret"
    SALESFORCE_DOMAIN: str = "login"

    # Raw Storage Configuration
    RAW_STORAGE_TYPE: str = "local"  # 'local' or 's3'
    RAW_STORAGE_PATH: str = "./raw_data"

    # AWS Credentials (Optional, used if RAW_STORAGE_TYPE is 's3')
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "my-enterprise-etl-bucket"

    # Slack Alerts Webhook
    SLACK_WEBHOOK_URL: Optional[str] = None

# Global settings instance
settings = Settings()
