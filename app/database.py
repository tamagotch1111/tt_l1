from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./calendar.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    full_name = Column(String)
    role = Column(String, default="user")

class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    employee_name = Column(String, index=True)
    shift_type = Column(String, nullable=True)
    is_vacation = Column(Boolean, default=False)
    is_sick = Column(Boolean, default=False)

class DutyAssignment(Base):
    __tablename__ = "duty_assignments"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    system = Column(String, index=True)
    slot = Column(String, index=True)
    employee_name = Column(String)

class Manager(Base):
    __tablename__ = "managers"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String, unique=True, index=True)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Добавляем руководителей по умолчанию, если таблица пуста
    if db.query(Manager).count() == 0:
        for name in ["Стрельникова Елена", "Малахова Алёна"]:
            if not db.query(Manager).filter(Manager.employee_name == name).first():
                db.add(Manager(employee_name=name))
        db.commit()
    db.close()
