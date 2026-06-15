from app.db import models
from app.db.base import Base
from app.db.session import engine

def init_db() -> None:
    # Import all modules here that might define models so that
    # they will be registered properly on the metadata. Otherwise
    # you will have to import them first before calling init_db()
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()