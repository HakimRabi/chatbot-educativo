"""
Database module - Centraliza la configuración de la base de datos
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

# Crear engine de SQLAlchemy
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verifica conexiones antes de usarlas
        pool_recycle=3600,   # Recicla conexiones después de 1 hora
        echo=False            # No mostrar SQL queries en logs
    )
    logger.info("✅ Database engine creado correctamente")
except Exception as e:
    logger.error(f"❌ Error creando database engine: {e}")
    engine = None

# Crear SessionLocal para crear sesiones de base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

def get_db():
    """
    Dependency para obtener una sesión de base de datos
    """
    if not SessionLocal:
        logger.warning("⚠️ Database SessionLocal no está disponible")
        return None
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
