import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DEFAULT_DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "var"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "app.db")
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH}"

def create_db_engine(database_url: str = DEFAULT_DATABASE_URL):
    """
    Creates an SQLite engine configured with:
    - PRAGMA journal_mode = WAL;
    - PRAGMA busy_timeout = 5000;
    - PRAGMA synchronous = NORMAL;
    - PRAGMA foreign_keys = ON;
    """
    # Ensure directory exists for file-based sqlite
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        db_file = database_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args={"timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    return engine

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
