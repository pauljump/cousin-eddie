"""
Database initialization utilities.
"""

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.company import CompanyModel
from src.models.signal import SignalModel
from src.core.company import UBER


def init_db(database_url: str = None):
    """
    Initialize database tables and TimescaleDB hypertables.

    Args:
        database_url: Optional database URL override
    """
    if database_url:
        engine = create_engine(database_url)
    else:
        from src.models.base import engine

    logger.info("Creating database tables...")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    logger.info("Tables created successfully")

    # Convert signals table to TimescaleDB hypertable
    try:
        with engine.connect() as conn:
            # Check if already a hypertable
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.hypertables
                    WHERE hypertable_name = 'signals'
                );
            """))
            is_hypertable = result.scalar()

            if not is_hypertable:
                logger.info("Converting signals table to TimescaleDB hypertable...")
                conn.execute(text("""
                    SELECT create_hypertable(
                        'signals',
                        'timestamp',
                        if_not_exists => TRUE
                    );
                """))
                conn.commit()
                logger.info("Signals table converted to hypertable successfully")
            else:
                logger.info("Signals table is already a hypertable")

    except Exception as e:
        logger.warning(f"Could not create hypertable (may not be using TimescaleDB): {e}")

    # Insert Uber company if not exists
    logger.info("Inserting Uber into companies table...")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(CompanyModel).filter(CompanyModel.id == UBER.id).first()
        if not existing:
            company = CompanyModel(
                id=UBER.id,
                ticker=UBER.ticker,
                name=UBER.name,
                cik=UBER.cik,
                sector=UBER.sector,
                industry=UBER.industry,
                has_sec_filings=UBER.has_sec_filings,
                has_app=UBER.has_app,
                has_physical_locations=UBER.has_physical_locations,
                is_tech_company=UBER.is_tech_company,
                extra_metadata=UBER.metadata,
            )
            db.add(company)
            db.commit()
            logger.info(f"Inserted company: {UBER.ticker}")
        else:
            logger.info(f"Company {UBER.ticker} already exists")
    finally:
        db.close()

    logger.info("Database initialization complete!")
