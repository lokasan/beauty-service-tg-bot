from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    MASTER = "master"
    CLIENT = "client"


class AppointmentStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class NotificationType(enum.Enum):
    CONFIRMATION = "confirmation"
    REMINDER = "reminder"
    CANCELLATION = "cancellation"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.CLIENT)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    master_profile = relationship("MasterProfile", back_populates="user", uselist=False)
    appointments_as_client = relationship("Appointment", foreign_keys="Appointment.client_id", back_populates="client")


class MasterProfile(Base):
    __tablename__ = "master_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    unique_link = Column(String(255), unique=True, nullable=False, index=True)
    business_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    default_notification_hours = Column(Integer, default=24)  # За сколько часов напоминать
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="master_profile")
    services = relationship("Service", back_populates="master", cascade="all, delete-orphan")
    schedule_slots = relationship("ScheduleSlot", back_populates="master", cascade="all, delete-orphan")
    appointments = relationship("Appointment", foreign_keys="Appointment.master_id", back_populates="master_profile")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    master = relationship("MasterProfile", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_recurring = Column(Boolean, default=False)  # Для фиксированного расписания
    day_of_week = Column(Integer, nullable=True)  # 0-6 для повторяющихся слотов
    specific_date = Column(Date, nullable=True)  # Конкретная дата для индивидуального расписания
    is_day_off = Column(Boolean, default=False)  # Выходной день
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    master = relationship("MasterProfile", back_populates="schedule_slots")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.PENDING)
    client_name = Column(String(255), nullable=True)
    client_phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    master_profile = relationship("MasterProfile", foreign_keys=[master_id])
    client = relationship("User", foreign_keys=[client_id])
    service = relationship("Service", back_populates="appointments")
    notifications = relationship("Notification", back_populates="appointment")
    invoice = relationship("Invoice", back_populates="appointment", uselist=False, cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, nullable=False)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    appointment = relationship("Appointment", back_populates="notifications")


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    WAITING = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    master_id = Column(Integer, ForeignKey("master_profiles.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    amount = Column(Float, nullable=False)  # Сумма к оплате
    currency = Column(String(10), default="RUB")  # Валюта (по умолчанию рубли)
    description = Column(Text, nullable=True)  # Описание услуги
    
    # Данные платежной системы
    payment_id = Column(String(255), nullable=True, unique=True)  # ID платежа в PayMaster
    payment_url = Column(Text, nullable=True)  # Ссылка на оплату
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Метод оплаты
    payment_method = Column(String(50), nullable=True)  # card, sbp, и т.д.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointment = relationship("Appointment", back_populates="invoice")
    master_profile = relationship("MasterProfile", foreign_keys=[master_id])
    client = relationship("User", foreign_keys=[client_id])


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    message = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5
    created_at = Column(DateTime, default=datetime.utcnow)

