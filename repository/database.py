from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import pt_config

eng = create_engine(
    f"postgresql://{pt_config.DB_USER}:{pt_config.DB_PASSWORD}@"
    f"{pt_config.DB_HOST}:{pt_config.DB_PORT}/{pt_config.DB_NAME}"
)
autocommit_engine = eng.execution_options(isolation_level="AUTOCOMMIT")
SessionLocal = sessionmaker(bind=autocommit_engine)
Base = declarative_base()
