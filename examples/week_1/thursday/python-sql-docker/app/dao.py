import os
import psycopg2
import logging

from app.exceptions import DatabaseConnectionError, LogCreationError

# Initialize structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SystemLogDAO:
    """DAO layer abstraction managing operational payloads for system_logs"""

    def __init__(self):
        # read parameters provided by docker compose environment variables
        self.host = os.getenv("DB_HOST", "db")
        self.database = os.getenv("DB_NAME", "postgres")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "secret")
        self._ensure_table_exists()
    
    def _get_connection(self):
        try:
            return psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
        except psycopg2.OperationalError as err:
            logging.error(f"Failed to establish live connection database: {err}")
            raise DatabaseConnectionError("Database backend service is unreachable")
    
    def _ensure_table_exists(self):
        """Initializes database schema structurally if missing"""
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                           id SERIAL PRIMARY KEY,
                           host VARCHAR(50),
                           severity VARCHAR(20),
                           message TEXT
                           );
            """)
            connection.commit()
            logging.info("Schema integrity verified: system_logs table exists")
        except Exception as err:
            logging.critical(f"Failed to bootstrap application table schema: {err}")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def insert_log(self, host: str, severity: str, message: str):
        """Securely inserts log strings useing parameterized inputs."""
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            # Parameterized query execution
            query = "INSERT INTO system_logs (host, severity, message) VALUES (%s, %s, %s);"
            cursor.execute(query, (host, severity, message))
            connection.commit()
            logging.info(f"Successfully recorded structured log entry for host: {host}")
        except DatabaseConnectionError:
            raise
        except Exception as err:
            logging.error(f"Failed to execute target insert statement: {err}")
            raise LogCreationError("Data layer constraint violation occurred")
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def get_all_logs(self) -> list:
        """Fetches and handles database record sets cleanly"""
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT host, severity, message FROM system_logs ORDER BY id DESC;")
            records = cursor.fetchall()

            # map elements
            return [{"host": row[0], "severity": row[1], "message": row[2]} for row in records]
        except Exception as err:
            logging.error(f"Retrieval failure acoss data layers: {err}")
            return []
        finally:
            if cursor: cursor.close()
            if connection : connection.close()