import logging
import sys

from flask import Flask

from agent_package.config import IS_PRODUCTION, DevelopmentConfig, ProductionConfig
from agent_package.domain_layer.pk_storage_base import PKStorageBase
from agent_package.repository_layer.gemini_llm import GeminiLLM
from agent_package.repository_layer.openai_llm import OpenAiLLM
from agent_package.system_layer.databases_registry.mongo_db import MongoDB
from agent_package.system_layer.databases_registry.sqlite_db import SQLiteDB
from agent_package.system_layer.pk_storage.db_pk_storage import DBStorage

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

if IS_PRODUCTION:
    logger.info("Running in production mode")
    config_class = ProductionConfig
else:
    logger.info("Running in development mode")
    config_class = DevelopmentConfig

# Create an instance to access the validated values
config = config_class()

# Initialize MongoDB connection
db_connection = None

if config.PK_STORAGE_TYPE == "local":
    logger.info("Initializing SQLite storage for local mode")
    try:
        db_connection = SQLiteDB("local_orchestrator.db")
    except Exception as e:
        logger.error(f"Could not initialize SQLite: {e}")
        raise
    pk_storage: PKStorageBase = DBStorage(db_connection)

elif config.PK_STORAGE_TYPE == "mongodb":
    try:
        db_connection = MongoDB(
            config.MONGO_DB_NAME,
            config.MONGO_DB_USER,
            config.MONGO_DB_PASS,
            config.MONGO_DB_REST_URL,
        )
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB: {e}")
        logger.error("PK_STORAGE_TYPE is 'mongodb' but MongoDB connection failed!")
        raise

    if db_connection is None:
        raise ValueError("mongodb_instance is required for MongoDB storage type")
    pk_storage: PKStorageBase = DBStorage(db_connection)

else:
    raise ValueError(
        f"Invalid storage type: {config.PK_STORAGE_TYPE}. Must be 'local' or 'mongodb'"
    )

if config.LLM_PROVIDER == "gemini":
    llm = GeminiLLM(config.GEMINI_API_KEY, config.GEMINI_VERSION)
elif config.LLM_PROVIDER == "openai":
    llm = OpenAiLLM(config.OPENAI_API_KEY)


def create_app(config_object=config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    return app
