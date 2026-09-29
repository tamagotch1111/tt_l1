from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./data/calendar.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="employee") # admin, manager, employee
    is_active = Column(Boolean, default=True)

class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True, nullable=False)
    employee_name = Column(String, index=True, nullable=False)
    shift_type = Column(String, nullable=True)
    is_vacation = Column(Boolean, default=False)
    is_sick = Column(Boolean, default=False)

class DutyAssignment(Base):
    __tablename__ = "duty_assignments"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True, nullable=False)
    system = Column(String, nullable=False)
    slot = Column(String, nullable=False)
    employee_name = Column(String, nullable=False)

class Manager(Base):
    __tablename__ = "managers"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String, unique=True, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            conn.commit()
        except Exception:
            pass
