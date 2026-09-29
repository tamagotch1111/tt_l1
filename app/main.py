from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import date, datetime, timedelta
from collections import defaultdict
import shutil, os

from app.database import init_db, SessionLocal, ScheduleEntry, DutyAssignment, User, Manager
from app.auth import get_current_user, hash_password
from app.excel_parser import parse_schedule_excel

app = FastAPI(title="Duty Calendar")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        db.add(User(username="admin", password_hash=hash_password("admin123"), full_name="Главный Администратор", role="admin", is_active=True))
    else:
        admin_user.role = "admin"
        admin_user.is_active = True
    
    user_test = db.query(User).filter(User.username == "user").first()
    if not user_test:
        db.add(User(username="user", password_hash=hash_password("user123"), full_name="Красавин Артем", role="employee", is_active=True))
    
    db.commit()
    db.close()

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.post("/login")
def login_submit(response: Response, request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username.strip()).first()
    db.close()
    if not user or user.password_hash != hash_password(password):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Неверный логин или пароль"})
    if not getattr(user, "is_active", True):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Учетная запись заблокирована администратором"})
    
    res = RedirectResponse(url="/", status_code=303)
    res.set_cookie("user_session", user.username, httponly=True)
    return res

@app.get("/logout")
def logout():
    res = RedirectResponse(url="/login")
    res.delete_cookie("user_session")
    return res

@app.post("/api/change-password")
def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...), user = Depends(get_current_user)):
    if not user:
        return JSONResponse({"success": False, "error": "Не авторизован"}, status_code=401)
    if user.password_hash != hash_password(old_password):
        return JSONResponse({"success": False, "error": "Текущий пароль введен неверно"})
    if len(new_password) < 4:
        return JSONResponse({"success": False, "error": "Новый пароль слишком короткий (минимум 4 символа)"})
    
    db = SessionLocal()
    db_user = db.query(User).filter(User.id == user.id).first()
    db_user.password_hash = hash_password(new_password)
    db.commit()
    db.close()
    return JSONResponse({"success": True})

@app.get("/", response_class=HTMLResponse)
def index(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    today = date.today()
    db = SessionLocal()
    entries = db.query(ScheduleEntry).filter(ScheduleEntry.date == today).all()
    total_entries_count = db.query(ScheduleEntry).count()
    duties = db.query(DutyAssignment).filter(DutyAssignment.date == today).all()
    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    db.close()

    reg_data = {
        "МБ": {"main": None, "morning": None, "evening": None},
        "НРД": {"main": None, "morning": None, "evening": None},
        "НКЦ": {"main": None, "morning": None, "evening": None},
    }
    for d in duties:
        if d.system in reg_data:
            if d.slot == "day": reg_data[d.system]["main"] = d.employee_name
            elif d.slot == "morning": reg_data[d.system]["morning"] = d.employee_name
            elif d.slot == "evening": reg_data[d.system]["evening"] = d.employee_name

    relievers_raw = []
    for e in entries:
        if e.shift_type in ["08:00", "10:00", "с 8", "с 10"]:
            shift_label = "08:00" if "8" in e.shift_type else "10:00"
            relievers_raw.append((shift_label, e.employee_name))
    
    unique_relievers = list(set(relievers_raw))
    unique_relievers.sort(key=lambda x: (x[0], x[1]))
    formatted_relievers = [f"{name} ({shift})" for shift, name in unique_relievers]

    all_employees = sorted(list(set([row[0] for row in all_emps_db if row[0]])))
    manager_names = [m.employee_name for m in managers_db]

    managers_status = []
    if total_entries_count > 0 and entries:
        for m_name in manager_names:
            m_surname = m_name.strip().split()[0].lower() if m_name.strip() else ""
            m_entry = next((e for e in entries if e.employee_name and m_surname == e.employee_name.strip().split()[0].lower()), None)
            if m_entry:
                if m_entry.is_vacation: status_text = "🏖 В отпуске"
                elif m_entry.is_sick: status_text = "💊 На больничном"
                else: status_text = "09:00–18:00"
            else:
                status_text = "Выходной"
            managers_status.append({"name": m_name, "status": status_text})

    blocks = {
        "reg": reg_data,
        "s7": list(set([e.employee_name for e in entries if e.shift_type in ["07:00", "с 7"]])),
        "s12": list(set([e.employee_name for e in entries if e.shift_type in ["12:00", "с 12"]])),
        "s15": list(set([e.employee_name for e in entries if e.shift_type in ["15:00", "с 15"]])),
        "relievers": formatted_relievers,
        "vacation": list(set([e.employee_name for e in entries if e.is_vacation])),
        "sick": list(set([e.employee_name for e in entries if e.is_sick])),
        "managers_status": managers_status,
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user, 
            "blocks": blocks, 
            "today": today.strftime("%d.%m.%Y"),
            "all_employees": all_employees,
            "manager_names": manager_names
        }
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, tab: str = "schedule", user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/")
    db = SessionLocal()
    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    all_employees = sorted(list(set([row[0] for row in all_emps_db if row[0]])))
    managers_list = [m.employee_name for m in managers_db]

    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={
            "user": user, 
            "msg": None, 
            "tab": tab,
            "all_employees": all_employees,
            "managers_list": managers_list,
            "users_list": users_list
        }
    )

@app.post("/admin/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    user = Depends(get_current_user)
):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    existing = db.query(User).filter(User.username == username.strip()).first()
    if existing:
        msg = f"Пользователь с логином {username} уже существует."
        success = False
    else:
        new_u = User(
            username=username.strip(),
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            role=role,
            is_active=True
        )
        db.add(new_u)
        db.commit()
        msg = f"Пользователь {full_name} успешно создан."
        success = True

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "users",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

# Редактирование профиля (ФИО и логин)
@app.post("/admin/users/edit")
def edit_user(
    request: Request,
    user_id: int = Form(...),
    full_name: str = Form(...),
    username: str = Form(...),
    user = Depends(get_current_user)
):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    
    db = SessionLocal()
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        msg = "Пользователь не найден."
        success = False
    else:
        new_username = username.strip()
        existing = db.query(User).filter(User.username == new_username, User.id != user_id).first()
        if existing:
            msg = f"Логин @{new_username} уже занят другим пользователем."
            success = False
        else:
            target_user.full_name = full_name.strip()
            target_user.username = new_username
            db.commit()
            msg = f"Данные сотрудника {target_user.full_name} успешно обновлены."
            success = True

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    response = templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "users",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )
    if success and user.id == user_id:
        response.set_cookie("user_session", target_user.username, httponly=True)
    return response

@app.post("/admin/users/toggle-block")
def toggle_user_block(request: Request, user_id: int = Form(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    if user.id == user_id:
        msg = "Нельзя заблокировать свою собственную учетную запись."
        success = False
    else:
        db = SessionLocal()
        target_user = db.query(User).filter(User.id == user_id).first()
        if target_user:
            current_active = getattr(target_user, "is_active", True)
            target_user.is_active = not current_active
            db.commit()
            status_str = "разблокирован" if target_user.is_active else "заблокирован"
            msg = f"Пользователь {target_user.full_name} успешно {status_str}."
            success = True
        else:
            msg = "Пользователь не найден."
            success = False
        db.close()

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "users",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/users/update-role")
def update_user_role(request: Request, user_id: int = Form(...), new_role: str = Form(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        if target_user.id == user.id and new_role != user.role:
            msg = "Вы не можете изменить свою собственную роль."
            success = False
        else:
            target_user.role = new_role
            db.commit()
            msg = f"Роль пользователя {target_user.full_name} изменена."
            success = True
    else:
        msg = "Пользователь не найден."
        success = False

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "users",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/users/reset-password")
def reset_user_password(request: Request, user_id: int = Form(...), new_password: str = Form(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.password_hash = hash_password(new_password)
        db.commit()
        msg = f"Пароль для пользователя {target_user.full_name} успешно обновлен."
        success = True
    else:
        msg = "Пользователь не найден."
        success = False

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "users",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/users/delete")
def delete_user(request: Request, user_id: int = Form(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    if user.id == user_id:
        msg = "Нельзя удалить свою собственную учетную запись."
        success = False
    else:
        db = SessionLocal()
        u = db.query(User).filter(User.id == user_id).first()
        if u:
            db.delete(u)
            db.commit()
            msg = f"Пользователь {u.full_name} удален."
            success = True
        else:
            msg = "Пользователь не найден."
            success = False
        db.close()

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "users",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/clear-schedule")
def clear_schedule(request: Request, user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    try:
        db.query(ScheduleEntry).delete()
        db.query(DutyAssignment).delete()
        db.commit()
        msg = "График смен и дежурств полностью очищен."
        success = True
    except Exception as e:
        db.rollback()
        msg = f"Ошибка при очистке: {str(e)}"
        success = False

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "schedule",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/add-manager")
def add_manager(request: Request, employee_name: str = Form(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    if employee_name and not db.query(Manager).filter(Manager.employee_name == employee_name).first():
        db.add(Manager(employee_name=employee_name))
        db.commit()
        msg = f"Руководитель {employee_name} добавлен."
        success = True
    else:
        msg = "Руководитель уже существует или не указан."
        success = False
    
    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "schedule",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/delete-manager")
def delete_manager(request: Request, employee_name: str = Form(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    mgr = db.query(Manager).filter(Manager.employee_name == employee_name).first()
    if mgr:
        db.delete(mgr)
        db.commit()
        msg = f"Руководитель {employee_name} удален."
        success = True
    else:
        msg = "Руководитель не найден."
        success = False

    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "schedule",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

@app.post("/admin/add-entry")
def add_entry(
    request: Request,
    date_val: str = Form(...),
    employee_name: str = Form(...),
    shift_type: str = Form(...),
    duty_system: str = Form(...),
    status: str = Form(...),
    user = Depends(get_current_user)
):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    
    db = SessionLocal()
    try:
        d = datetime.strptime(date_val, "%Y-%m-%d").date()
        entry = db.query(ScheduleEntry).filter(ScheduleEntry.date == d, ScheduleEntry.employee_name == employee_name).first()
        if not entry:
            entry = ScheduleEntry(date=d, employee_name=employee_name)
            db.add(entry)
        
        entry.shift_type = shift_type if shift_type != "none" else None
        
        if status == "vacation":
            entry.is_vacation, entry.is_sick = True, False
        elif status == "sick":
            entry.is_vacation, entry.is_sick = False, True
        else:
            entry.is_vacation, entry.is_sick = False, False

        if duty_system != "none":
            duty = db.query(DutyAssignment).filter(DutyAssignment.date == d, DutyAssignment.system == duty_system).first()
            if not duty:
                duty = DutyAssignment(date=d, system=duty_system, slot="day", employee_name=employee_name)
                db.add(duty)
            else:
                duty.employee_name = employee_name

        db.commit()
        msg = "Запись успешно сохранена."
        success = True
    except Exception as e:
        db.rollback()
        msg = f"Ошибка: {str(e)}"
        success = False
    
    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": success, "tab": "schedule",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )

def to_short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1][0]}."
    return full_name

def group_consecutive_dates(date_list):
    if not date_list:
        return []
    sorted_dates = sorted(date_list)
    ranges = []
    start = sorted_dates[0]
    prev = sorted_dates[0]

    for d in sorted_dates[1:]:
        if d == prev + timedelta(days=1):
            prev = d
        else:
            ranges.append((start, prev))
            start = d
            prev = d
    ranges.append((start, prev))
    return ranges

@app.get("/api/events")
def get_events(start: str, end: str, user = Depends(get_current_user)):
    if not user:
        return JSONResponse([], status_code=401)
    
    db = SessionLocal()
    s_date = datetime.fromisoformat(start.split('T')[0]).date()
    e_date = datetime.fromisoformat(end.split('T')[0]).date()
    entries = db.query(ScheduleEntry).filter(ScheduleEntry.date >= s_date, ScheduleEntry.date <= e_date).all()
    db.close()

    events = []
    seen = set()
    vacation_days = defaultdict(list)
    sick_days = defaultdict(list)
    weeks_with_absences = set()

    for item in entries:
        dedup_key = (item.employee_name, item.date)
        if dedup_key in seen: continue
        seen.add(dedup_key)

        raw_et = str(item.shift_type or "").strip()
        is_vac = bool(item.is_vacation) or (raw_et.lower() in ("о", "от", "отпуск", "vacation"))
        is_sk = bool(item.is_sick) or (raw_et.lower() in ("б", "больничн", "больничный", "sick"))

        if is_vac:
            vacation_days[item.employee_name].append(item.date)
            w_start = item.date - timedelta(days=item.date.weekday())
            weeks_with_absences.add(w_start)
            continue
        if is_sk:
            sick_days[item.employee_name].append(item.date)
            w_start = item.date - timedelta(days=item.date.weekday())
            weeks_with_absences.add(w_start)
            continue

        short_fio = to_short_name(item.employee_name)

        if "12" in raw_et:
            order, color, title_text, cls = 3, "#0284c7", f"{short_fio} (12:00)", "fc-shift-12"
            evt_category = "12:00"
        elif "15" in raw_et:
            order, color, title_text, cls = 4, "#7c3aed", f"{short_fio} (15:00)", "fc-shift-15"
            evt_category = "15:00"
        elif "10" in raw_et:
            order, color, title_text, cls = 6, "#9b0d23", f"{short_fio} (10:00)", "fc-shift-reliever font-bold"
            evt_category = "reliever"
        elif "7" in raw_et:
            order, color, title_text, cls = 1, "#dc2626", f"{short_fio} (07:00)", "fc-shift-7"
            evt_category = "07:00"
        elif "9" in raw_et:
            order, color, title_text, cls = 2, "#475569", f"{short_fio} (09:00)", "fc-shift-9"
            evt_category = "09:00"
        elif "8" in raw_et:
            order, color, title_text, cls = 5, "#c8102e", f"{short_fio} (08:00)", "fc-shift-reliever font-bold"
            evt_category = "reliever"
        else:
            continue

        events.append({
            "title": title_text,
            "start": str(item.date),
            "allDay": True,
            "backgroundColor": color,
            "borderColor": color,
            "className": cls,
            "order": order,
            "extendedProps": {
                "full_name": item.employee_name,
                "shift": "08:00" if "8" in raw_et else ("10:00" if "10" in raw_et else raw_et),
                "category": evt_category,
                "order": order
            }
        })

    for w_start in weeks_with_absences:
        w_end = w_start + timedelta(days=7)
        events.append({
            "title": "",
            "start": str(w_start),
            "end": str(w_end),
            "allDay": True,
            "backgroundColor": "transparent",
            "borderColor": "transparent",
            "className": "fc-absence-divider",
            "order": 6.5,
            "extendedProps": {
                "is_divider": True,
                "category": "divider",
                "order": 6.5
            }
        })

    for emp_name, dates in sick_days.items():
        short_fio = to_short_name(emp_name)
        for r_start, r_end in group_consecutive_dates(dates):
            events.append({
                "title": f"💊 {short_fio}",
                "start": str(r_start),
                "end": str(r_end + timedelta(days=1)),
                "allDay": True,
                "backgroundColor": "#ea580c",
                "borderColor": "#c2410c",
                "className": "fc-event-absence fc-event-sick",
                "order": 7,
                "extendedProps": {
                    "full_name": emp_name,
                    "shift": "Больничный",
                    "category": "sick",
                    "order": 7
                }
            })

    for emp_name, dates in vacation_days.items():
        short_fio = to_short_name(emp_name)
        for r_start, r_end in group_consecutive_dates(dates):
            events.append({
                "title": f"🏖 {short_fio}",
                "start": str(r_start),
                "end": str(r_end + timedelta(days=1)),
                "allDay": True,
                "backgroundColor": "#d97706",
                "borderColor": "#b45309",
                "className": "fc-event-absence fc-event-vacation",
                "order": 8,
                "extendedProps": {
                    "full_name": emp_name,
                    "shift": "Отпуск",
                    "category": "vacation",
                    "order": 8
                }
            })

    events.sort(key=lambda x: x["order"])
    return events

@app.get("/api/day-details")
def get_day_details(date_str: str, user = Depends(get_current_user)):
    if not user:
        return JSONResponse({}, status_code=401)
    
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    db = SessionLocal()
    entries = db.query(ScheduleEntry).filter(ScheduleEntry.date == target_date).all()
    duties = db.query(DutyAssignment).filter(DutyAssignment.date == target_date).all()
    db.close()

    time_priority = {
        "07:00": 1, "с 7": 1, "09:00": 2, "с 9": 2,
        "12:00": 3, "с 12": 3, "15:00": 4, "с 15": 4,
        "08:00": 5, "с 8": 5, "10:00": 6, "с 10": 6
    }
    
    formatted_entries = []
    for e in entries:
        raw_s = e.shift_type or ""
        norm_s = "07:00" if "7" in raw_s else ("09:00" if "9" in raw_s else ("12:00" if "12" in raw_s else ("15:00" if "15" in raw_s else ("08:00" if "8" in raw_s else ("10:00" if "10" in raw_s else raw_s)))))
        formatted_entries.append({
            "fio": e.employee_name,
            "shift": norm_s if not (e.is_vacation or e.is_sick) else None,
            "vacation": e.is_vacation,
            "sick": e.is_sick,
            "order": time_priority.get(norm_s, 99)
        })

    formatted_entries.sort(key=lambda x: x["order"])

    slot_priority = {"morning": 1, "day": 2, "evening": 3}
    sys_priority = {"МБ": 1, "НРД": 2, "НКЦ": 3}

    formatted_duties = [
        {"system": d.system, "slot": d.slot, "fio": d.employee_name}
        for d in duties
    ]
    formatted_duties.sort(key=lambda d: (slot_priority.get(d["slot"], 99), sys_priority.get(d["system"], 99)))

    return {
        "date": target_date.strftime("%d.%m.%Y"),
        "entries": formatted_entries,
        "duties": formatted_duties
    }

@app.post("/admin/upload-excel")
async def upload_excel(request: Request, file: UploadFile = File(...), user = Depends(get_current_user)):
    if not user or user.role not in ["admin", "manager"]:
        return RedirectResponse(url="/", status_code=303)
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    ok, msg = parse_schedule_excel(tmp_path)
    if os.path.exists(tmp_path): os.remove(tmp_path)
    
    db = SessionLocal()
    all_emps_db = db.query(ScheduleEntry.employee_name).distinct().all()
    managers_db = db.query(Manager).all()
    users_list = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        request=request, name="admin.html", 
        context={
            "user": user, "msg": msg, "success": ok, "tab": "schedule",
            "all_employees": sorted(list(set([r[0] for r in all_emps_db if r[0]]))),
            "managers_list": [m.employee_name for m in managers_db],
            "users_list": users_list
        }
    )
