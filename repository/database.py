from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import pt_config

Engine = create_engine(
    f"postgresql://{pt_config.DB_USER}:{pt_config.DB_PASSWORD}@"
    f"{pt_config.DB_HOST}:{pt_config.DB_PORT}/{pt_config.DB_NAME}"
)
SessionLocal = sessionmaker(bind=Engine)
Base = declarative_base()
