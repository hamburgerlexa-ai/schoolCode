from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from models import db, User, Assignment, Submission, ActivityLog

app = Flask(__name__, template_folder='../templates', static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///coding_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создание таблиц БД
with app.app_context():
    db.create_all()
    
    # Создаем тестового учителя если нет пользователей
    if not User.query.first():
        teacher = User(
            username='teacher',
            password=generate_password_hash('teacher123'),
            role='teacher'
        )
        db.session.add(teacher)
        
        # Создаем тестовых учеников
        for i in range(1, 6):
            student = User(
                username=f'student{i}',
                password=generate_password_hash('student123'),
                role='student',
                class_name='9A'
            )
            db.session.add(student)
        
        db.session.commit()
        print("Создан тестовый учитель: username='teacher', password='teacher123'")
        print("Созданы тестовые ученики: student1-student5, password='student123'")


@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ==================== УЧИТЕЛЬ ====================

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('student_dashboard'))
    
    assignments = Assignment.query.filter_by(teacher_id=current_user.id).order_by(Assignment.created_at.desc()).all()
    return render_template('teacher_dashboard.html', assignments=assignments)


@app.route('/teacher/assignment/create', methods=['GET', 'POST'])
@login_required
def create_assignment():
    if current_user.role != 'teacher':
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        assignment = Assignment(
            title=request.form.get('title'),
            description=request.form.get('description'),
            starter_code=request.form.get('starter_code'),
            language=request.form.get('language', 'python'),
            duration_minutes=int(request.form.get('duration_minutes', 45)),
            class_name=request.form.get('class_name'),
            teacher_id=current_user.id
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Задание создано!', 'success')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('create_assignment.html')


@app.route('/teacher/assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    if current_user.role != 'teacher':
        return redirect(url_for('student_dashboard'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    return render_template('view_assignment.html', assignment=assignment, submissions=submissions)


@app.route('/teacher/submission/<int:submission_id>', methods=['GET', 'POST'])
@login_required
def grade_submission(submission_id):
    if current_user.role != 'teacher':
        return redirect(url_for('student_dashboard'))
    
    submission = Submission.query.get_or_404(submission_id)
    
    if request.method == 'POST':
        submission.score = int(request.form.get('score'))
        submission.feedback = request.form.get('feedback')
        db.session.commit()
        flash('Оценка выставлена!', 'success')
        return redirect(url_for('view_assignment', assignment_id=submission.assignment_id))
    
    # Получаем логи активности
    activity_logs = ActivityLog.query.filter_by(submission_id=submission_id).order_by(ActivityLog.timestamp).all()
    return render_template('grade_submission.html', submission=submission, activity_logs=activity_logs)


@app.route('/teacher/monitoring')
@login_required
def teacher_monitoring():
    """Мониторинг активных работ в реальном времени"""
    if current_user.role != 'teacher':
        return redirect(url_for('student_dashboard'))
    
    # Получаем все активные задания для классов учителя
    active_assignments = Assignment.query.filter(
        Assignment.teacher_id == current_user.id,
        Assignment.created_at > datetime.utcnow() - timedelta(hours=2)
    ).all()
    
    active_submissions = []
    for assignment in active_assignments:
        subs = Submission.query.filter_by(assignment_id=assignment.id).all()
        active_submissions.extend(subs)
    
    return render_template('monitoring.html', submissions=active_submissions)


# ==================== УЧЕНИК ====================

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('teacher_dashboard'))
    
    assignments = Assignment.query.filter(
        (Assignment.class_name == current_user.class_name) | 
        (Assignment.class_name == None)
    ).order_by(Assignment.created_at.desc()).all()
    
    # Проверяем какие задания уже выполнены
    completed_ids = [s.assignment_id for s in Submission.query.filter_by(student_id=current_user.id).all()]
    
    return render_template('student_dashboard.html', assignments=assignments, completed_ids=completed_ids)


@app.route('/student/assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def do_assignment(assignment_id):
    if current_user.role != 'student':
        return redirect(url_for('teacher_dashboard'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Проверяем есть ли уже выполненная работа
    existing_submission = Submission.query.filter_by(
        student_id=current_user.id,
        assignment_id=assignment_id
    ).first()
    
    if request.method == 'POST':
        code = request.form.get('code')
        time_spent = int(request.form.get('time_spent', 0))
        violations = int(request.form.get('violations', 0))
        
        if existing_submission:
            existing_submission.code = code
            existing_submission.time_spent_seconds = time_spent
            existing_submission.violations_count = violations
            existing_submission.submitted_at = datetime.utcnow()
        else:
            submission = Submission(
                code=code,
                student_id=current_user.id,
                assignment_id=assignment_id,
                time_spent_seconds=time_spent,
                violations_count=violations
            )
            db.session.add(submission)
        
        db.session.commit()
        flash('Работа отправлена!', 'success')
        return redirect(url_for('student_dashboard'))
    
    starter_code = existing_submission.code if existing_submission else (assignment.starter_code or '# Напишите ваш код здесь\n')
    
    return render_template('do_assignment.html', 
                         assignment=assignment, 
                         starter_code=starter_code,
                         existing_submission=existing_submission)


@app.route('/student/auto-save', methods=['POST'])
@login_required
def auto_save():
    """Автосохранение работы"""
    data = request.json
    assignment_id = data.get('assignment_id')
    code = data.get('code')
    time_spent = data.get('time_spent', 0)
    violations = data.get('violations', 0)
    
    submission = Submission.query.filter_by(
        student_id=current_user.id,
        assignment_id=assignment_id
    ).first()
    
    if submission:
        submission.code = code
        submission.time_spent_seconds = time_spent
        submission.violations_count = violations
        submission.auto_saved = True
    else:
        submission = Submission(
            code=code,
            student_id=current_user.id,
            assignment_id=assignment_id,
            time_spent_seconds=time_spent,
            violations_count=violations,
            auto_saved=True
        )
        db.session.add(submission)
    
    db.session.commit()
    return jsonify({'status': 'saved'})


@app.route('/student/log-activity', methods=['POST'])
@login_required
def log_activity():
    """Логирование активности ученика"""
    data = request.json
    event_type = data.get('event_type')
    details = data.get('details', '')
    assignment_id = data.get('assignment_id')
    
    # Находим текущую работу
    submission = Submission.query.filter_by(
        student_id=current_user.id,
        assignment_id=assignment_id
    ).first()
    
    activity_log = ActivityLog(
        event_type=event_type,
        details=details,
        user_id=current_user.id,
        submission_id=submission.id if submission else None
    )
    db.session.add(activity_log)
    db.session.commit()
    
    return jsonify({'status': 'logged'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
