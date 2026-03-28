from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Модель пользователя (учитель или ученик)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' или 'student'
    class_name = db.Column(db.String(50))  # Класс для учеников
    
    assignments = db.relationship('Assignment', backref='teacher', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)
    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True)


class Assignment(db.Model):
    """Модель задания"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    starter_code = db.Column(db.Text)  # Начальный код для задания
    language = db.Column(db.String(20), default='python')
    duration_minutes = db.Column(db.Integer, default=45)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_name = db.Column(db.String(50))  # Для какого класса
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True)


class Submission(db.Model):
    """Модель выполненной работы"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer)  # Оценка
    feedback = db.Column(db.Text)  # Комментарий учителя
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    
    # Данные мониторинга
    time_spent_seconds = db.Column(db.Integer)
    violations_count = db.Column(db.Integer, default=0)
    auto_saved = db.Column(db.Boolean, default=False)
    
    activity_logs = db.relationship('ActivityLog', backref='submission', lazy=True)


class ActivityLog(db.Model):
    """Журнал активности ученика во время выполнения задания"""
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # 'tab_switch', 'blur', 'copy', 'idle'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)  # Дополнительная информация
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'))
