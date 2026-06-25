class DatabaseConnectionError(Exception):
    """Raised when the application cannot reach the PostgreSQL database instance."""
    pass

class LogCreationError(Exception):
    """Raised when an insertion operation violates constraints or fails."""
    pass