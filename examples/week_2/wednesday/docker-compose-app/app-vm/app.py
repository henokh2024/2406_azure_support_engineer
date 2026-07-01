import os
import logging
import psycopg2
from fastapi import FastAPI, HTTPException
from azure.identity import DefaultAzureCredential

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web-app")

app = FastAPI(title="SRE Demo")

# Read Database connection details from Environment Variables
DB_HOST = os.getenv("DB_HOST", "10.0.2.4")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "inventory")
DB_USER = os.getenv("DB_USER", "dbuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "SecretLocalPassword2026!")
DB_AUTH_MODE = os.getenv("DB_AUTH_MODE", "sql-auth").lower()

def get_db_connection():
    if DB_AUTH_MODE == "azure-ad":
        logger.info("Attempting to retrieve Azure AD Access Token from Managed Identity")

        try:
            # Initialize the DefaultAzureCredential which checks:
            # 1. Environmnet Variables (Client id/secret)
            # 2. Managed Identity (IMDS endpoint on Azure VM)
            # 3. Azure CLI Credentials
            credential = DefaultAzureCredential()

            # The resource scope for Azure Database for Postgresql flexible server
            token_scope = "https://ossrdbms-aad.database.windows.net/.default"
            token_obj = credential.get_token(token_scope)

            # For PostgreSQL, the acquired AAD access token is used directly as the password
            db_password = token_obj.token
            logger.info("Successfully retrieved Azure AD OAuth2 Access Token")
        except Exception as e:
            logger.error(f"Failed to retrieve Aure AD Token: {str(e)}")
            raise RuntimeError(f"Azure AD Token Retrieval Failed: {str(e)}")
    else:
        # Fallback/Default: Standard SQL Authentication
        logger.info("Using standard username/password (SQL Auth) credentials")
        db_password = DB_PASSWORD
    
    try:
        # Establish PostgreSQL connection
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=db_password,
            # For Azure SQL/PostgreSQL, SSL is typically required
            sslmode="require" if DB_AUTH_MODE == "azure-ad" else "prefer",
            connect_timeout=5 # 5 seconds connection timeout
        )
        logger.info("Database connection successfully established")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {str(e)}")
        raise e

@app.get("/")
def read_root():
    return{
        "status": "Online",
        "configuration": {
            "db_host": DB_HOST,
            "db_port": DB_PORT,
            "db_name": DB_NAME,
            "db_user": DB_USER,
            "auth_mode": DB_AUTH_MODE,
        },
        "description": "lorem Ipsum"
    }

@app.get("/health")
def health_check():
    return  {"status": "healthy"}

@app.get("/db-check")
def db_check():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        cursor.close()

        return {
            "database_connection": "SUCCESS",
            "postgres_version": db_version[0],
            "auth_method_used": DB_AUTH_MODE
        }
    except Exception as e:
        logger.error(f"Failed database connectivity verification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "database_connection": "FAILED",
                "reason": str(e)
            }
        )
    finally:
        if conn:
            conn.close()

