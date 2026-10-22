from typing import Iterator
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, Session
from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)


# Enable foreign keys for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(SessionFactory)
Base = declarative_base()


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def configure_db(db_url: str) -> None:
    """Reconfigures the database engine and session factory (useful for isolated unit tests)."""
    global engine, SessionFactory, SessionLocal
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        echo=False
    )
    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    SessionLocal = scoped_session(SessionFactory)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def init_db() -> None:
    """Create all tables if they do not exist, and migrate columns if needed."""
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Automatic non-destructive column migration for SQLite
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(invoices)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "reference_invoice_id" not in columns:
                conn.execute(text(
                    "ALTER TABLE invoices ADD COLUMN reference_invoice_id "
                    "INTEGER REFERENCES invoices(id) ON DELETE SET NULL"
                ))
            if columns and "annulment_reason" not in columns:
                conn.execute(text(
                    "ALTER TABLE invoices ADD COLUMN annulment_reason VARCHAR(250)"
                ))
            conn.commit()
    except Exception:
        pass
