import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .email_sender import send_verification_code
from .models import Task, User
from .schemas import (
    SendCodeRequest,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    VerifyCode,
)
from .security import hash_password, verify_password

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Railway Task + Users API",
    version="1.2.0",
    description="FastAPI + PostgreSQL on Railway with email verification.",
)

# --- CORS ---------------------------------------------------------------
_origins_env = os.getenv("CORS_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

CODE_TTL_MINUTES = 10


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


# --- Health -------------------------------------------------------------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# --- Tasks --------------------------------------------------------------

@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return list(db.scalars(select(Task).order_by(Task.id)).all())


@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(title=payload.title, description=payload.description)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@app.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    db.delete(task)
    db.commit()


# --- Users --------------------------------------------------------------

def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def _issue_code(user: User, db: Session) -> bool:
    """Генерирует код, сохраняет и пытается отправить. Возвращает статус отправки."""
    code = _generate_code()
    user.verification_code = code
    user.verification_expires = datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES)
    db.commit()
    return send_verification_code(user.email, code)


@app.post(
    "/api/users/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _issue_code(user, db)
    db.refresh(user)
    return user


@app.post("/api/users/login", response_model=UserResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return user


@app.post("/api/users/send-code")
def send_code(payload: SendCodeRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.email_verified:
        return {"status": "already_verified"}

    sent = _issue_code(user, db)
    return {"status": "sent" if sent else "failed"}


@app.post("/api/users/verify", response_model=UserResponse)
def verify_email(payload: VerifyCode, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.email_verified:
        return user
    if not user.verification_code or not user.verification_expires:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Код не запрошен")
    if user.verification_expires < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Код истёк, запросите новый")
    if user.verification_code != payload.code.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неверный код")

    user.email_verified = True
    user.verification_code = None
    user.verification_expires = None
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return _get_user_or_404(db, user_id)


@app.put("/api/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    if (new_email := data.get("email")) is not None:
        new_email = new_email.strip().lower()
        if new_email != user.email:
            clash = db.scalar(select(User).where(User.email == new_email))
            if clash is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
            user.email = new_email
            # При смене email сбрасываем подтверждение
            user.email_verified = False
            _issue_code(user, db)

    if (new_name := data.get("name")) is not None:
        user.name = new_name.strip()
    if (new_pass := data.get("password")):
        user.password_hash = hash_password(new_pass)

    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    db.delete(user)
    db.commit()