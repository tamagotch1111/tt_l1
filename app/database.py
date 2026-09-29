from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/calendar.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ScheduleEntry(Base):
    __tablename__ = "schedule"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    employee_name = Column(String, index=True)
    shift_type = Column(String, nullable=True)
    is_vacation = Column(Boolean, default=False)
    is_sick = Column(Boolean, default=False)

class DutyAssignment(Base):
    __tablename__ = "duties"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    system = Column(String)
    slot = Column(String)
    employee_name = Column(String)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    full_name = Column(String)
    role = Column(String, default="employee")
    is_active = Column(Boolean, default=True)

class Manager(Base):
    __tablename__ = "managers"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String, unique=True)

def init_db():
    Base.metadata.create_all(bind=engine)
