import os
import json
from datetime import datetime
from typing import Any, Dict, List
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger("Storage")

class BaseStorage:
    """
    Interface for data storage engines.
    """
    def write(self, source: str, entity: str, run_id: str, data: List[Dict[str, Any]]) -> str:
        """
        Persists raw JSON extract and returns the file path/URI string.
        """
        raise NotImplementedError("Storage engines must implement write()")

class LocalStorage(BaseStorage):
    """
    Local filesystem storage engine.
    """
    def __init__(self, base_path: str):
        self.base_path = base_path

    def write(self, source: str, entity: str, run_id: str, data: List[Dict[str, Any]]) -> str:
        today = datetime.now(timezone_utc := datetime.now().astimezone().tzinfo).strftime("%Y-%m-%d")
        dir_path = os.path.join(self.base_path, source.lower(), entity.lower(), today)
        os.makedirs(dir_path, exist_ok=True)
        
        file_path = os.path.join(dir_path, f"run_{run_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Raw raw data persisted to local path: {file_path}")
        return file_path

class S3Storage(BaseStorage):
    """
    AWS S3 bucket storage engine with an automatic local fallback mechanism.
    """
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3_client = None
        try:
            import boto3
            # Attempt instantiation using configured keys first
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_DEFAULT_REGION
                )
            else:
                self.s3_client = boto3.client("s3")
        except ImportError:
            logger.warning("boto3 library is not installed. Falling back to LocalStorage.")
        except Exception as e:
            logger.warning(f"Failed to initialize AWS S3 client: {e}. Falling back to LocalStorage.")

    def write(self, source: str, entity: str, run_id: str, data: List[Dict[str, Any]]) -> str:
        if not self.s3_client:
            fallback = LocalStorage(settings.RAW_STORAGE_PATH)
            return fallback.write(source, entity, run_id, data)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"raw/{source.lower()}/{entity.lower()}/{today}/run_{run_id}.json"
        
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json_str.encode("utf-8"),
                ContentType="application/json"
            )
            s3_uri = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Raw raw data persisted to S3: {s3_uri}")
            return s3_uri
        except Exception as e:
            logger.error(f"Failed writing raw data to S3: {e}. Falling back to LocalStorage.")
            fallback = LocalStorage(settings.RAW_STORAGE_PATH)
            return fallback.write(source, entity, run_id, data)

def get_storage() -> BaseStorage:
    """
    Returns the appropriate Storage Engine based on configuration.
    """
    if settings.RAW_STORAGE_TYPE.lower() == "s3":
        return S3Storage(settings.S3_BUCKET_NAME)
    return LocalStorage(settings.RAW_STORAGE_PATH)
