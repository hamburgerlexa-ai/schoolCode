"""
School Coding Platform - Main Application
Production-ready Flask application with authentication, assignments, and anti-cheat monitoring
"""
import os
from datetime import datetime, timedelta
import csv
import io
import uuid
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from models import db, User, ClassGroup, Topic, Assignment, Submission, ActivityLog, Grade, Rubric, init_db, ClassMember

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///school_platform.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = os.environ.get('WTF_CSRF_ENABLED', 'True').lower() == 'true'
app.config['WTF_CSRF_TIME_LIMIT'] = int(os.environ.get('WTF_CSRF_TIME_LIMIT', 3600))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 86400)))
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16777216))
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['DEFAULT_ASSIGNMENT_DURATION_MINUTES'] = int(os.environ.get('DEFAULT_ASSIGNMENT_DURATION_MINUTES', 60))
app.config['AUTOSAVE_INTERVAL_SECONDS'] = int(os.environ.get('AUTOSAVE_INTERVAL_SECONDS', 30))

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def log_activity(event_type, event_data=None, submission_id=None):
    """Log user activity for anti-cheat and analytics"""
    if not current_user.is_authenticated:
        return
    
    log = ActivityLog(
        user_id=current_user.id,
        submission_id=submission_id,
        event_type=event_type,
        event_data=str(event_data) if event_data else None,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500],
        page_url=request.url[:500]
    )
    db.session.add(log)
    db.session.commit()


@app.route('/')
def index():
    """Home page"""
    if current_user.is_authenticated:
        if current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Ваш аккаунт деактивирован. Обратитесь к администратору.', 'error')
                return render_template('login.html')
            
            login_user(user, remember=remember)
            log_activity('login')
            
            next_page = request.args.get('next')
            flash(f'Добро пожаловать, {user.full_name}!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """User logout"""
    log_activity('logout')
    logout_user()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', 'student')
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Имя пользователя должно быть не менее 3 символов')
        if not email or '@' not in email:
            errors.append('Введите корректный email')
        if not password or len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        if password != confirm_password:
            errors.append('Пароли не совпадают')
        
        # Check existing
        if User.query.filter_by(username=username).first():
            errors.append('Пользователь с таким именем уже существует')
        if User.query.filter_by(email=email).first():
            errors.append('Email уже зарегистрирован')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Create user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


# ============== Student Routes ==============

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    """Student dashboard with active assignments"""
    if current_user.role not in ['student', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    # Get user's class groups
    class_ids = [cm.class_group_id for cm in current_user.class_memberships]
    
    # Get available assignments
    assignments = Assignment.query.filter(
        Assignment.class_group_id.in_(class_ids),
        Assignment.is_published == True
    ).order_by(Assignment.created_at.desc()).all()
    
    # Get user's submissions
    submissions = Submission.query.filter_by(user_id=current_user.id).all()
    submission_map = {s.assignment_id: s for s in submissions}
    
    return render_template('student/dashboard.html', 
                         assignments=assignments, 
                         submissions=submission_map)


@app.route('/assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    """View assignment details and start working"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check permissions
    if current_user.role == 'student':
        class_ids = [cm.class_group_id for cm in current_user.class_memberships]
        if assignment.class_group_id not in class_ids:
            flash('У вас нет доступа к этому заданию', 'error')
            return redirect(url_for('student_dashboard'))
    
    # Check availability
    if not assignment.is_available:
        flash('Задание ещё недоступно или срок его выполнения истёк', 'error')
        return redirect(url_for('student_dashboard'))
    
    # Get or create submission
    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        user_id=current_user.id,
        is_final=False
    ).first()
    
    if not submission:
        # Create new submission
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=assignment.duration_minutes)
        
        submission = Submission(
            assignment_id=assignment_id,
            user_id=current_user.id,
            status='draft',
            started_at=now,
            expires_at=expires_at,
            max_score=assignment.max_score,
            code=assignment.starter_code or ''
        )
        db.session.add(submission)
        db.session.commit()
        
        log_activity('assignment_started', {'assignment_id': assignment_id}, submission.id)
    else:
        # Update expires_at if needed
        if submission.expires_at and submission.expires_at < datetime.utcnow():
            flash('Время выполнения задания истекло', 'warning')
            return redirect(url_for('submission_review', submission_id=submission.id))
    
    return render_template('student/assignment.html', 
                         assignment=assignment, 
                         submission=submission)


@app.route('/api/submission/<int:submission_id>/autosave', methods=['POST'])
@login_required
def autosave_submission(submission_id):
    """Autosave submission draft"""
    submission = Submission.query.get_or_404(submission_id)
    
    if submission.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if submission.status != 'draft':
        return jsonify({'error': 'Submission already submitted'}), 400
    
    data = request.get_json()
    submission.code = data.get('code', submission.code)
    submission.updated_at = datetime.utcnow()
    
    db.session.commit()
    log_activity('autosave', {'code_length': len(submission.code)}, submission.id)
    
    return jsonify({
        'success': True,
        'saved_at': submission.updated_at.isoformat()
    })


@app.route('/api/submission/<int:submission_id>/activity', methods=['POST'])
@login_required
def log_submission_activity(submission_id):
    """Log anti-cheat activity"""
    submission = Submission.query.get_or_404(submission_id)
    
    if submission.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    event_type = data.get('event_type', 'unknown')
    event_data = data.get('event_data', {})
    
    # Update suspicion metrics
    if event_type == 'tab_switch':
        submission.tab_switches += 1
        submission.suspicion_score = min(100, submission.suspicion_score + 10)
    elif event_type == 'fullscreen_exit':
        submission.fullscreen_exits += 1
        submission.suspicion_score = min(100, submission.suspicion_score + 15)
    elif event_type == 'devtools_attempt':
        submission.devtools_attempts += 1
        submission.suspicion_score = min(100, submission.suspicion_score + 20)
    
    db.session.commit()
    log_activity(event_type, event_data, submission_id)
    
    return jsonify({
        'success': True,
        'suspicion_score': submission.suspicion_score
    })


@app.route('/submission/<int:submission_id>/submit', methods=['POST'])
@login_required
def submit_work(submission_id):
    """Submit final work"""
    submission = Submission.query.get_or_404(submission_id)
    
    if submission.user_id != current_user.id:
        flash('У вас нет доступа к этой работе', 'error')
        return redirect(url_for('student_dashboard'))
    
    if submission.status != 'draft':
        flash('Работа уже отправлена', 'warning')
        return redirect(url_for('submission_review', submission_id=submission_id))
    
    # Check if expired
    if submission.is_expired:
        submission.status = 'expired'
        db.session.commit()
        flash('Время выполнения истекло. Работа помечена как просроченная.', 'warning')
        return redirect(url_for('submission_review', submission_id=submission_id))
    
    # Submit
    data = request.get_json() or {}
    submission.code = data.get('code', submission.code)
    submission.status = 'submitted'
    submission.submitted_at = datetime.utcnow()
    submission.is_final = True
    
    db.session.commit()
    log_activity('submit', {'code_length': len(submission.code)}, submission.id)
    
    flash('Работа успешно отправлена!', 'success')
    return redirect(url_for('submission_review', submission_id=submission_id))


@app.route('/submission/<int:submission_id>/review')
@login_required
def submission_review(submission_id):
    """Review submission status and results"""
    submission = Submission.query.get_or_404(submission_id)
    
    if submission.user_id != current_user.id and current_user.role != 'teacher':
        flash('У вас нет доступа к этой работе', 'error')
        return redirect(url_for('index'))
    
    return render_template('student/submission_review.html', submission=submission)


# ============== Teacher Routes ==============

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    """Teacher dashboard with classes and assignments"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    # Get teacher's classes
    class_groups = ClassGroup.query.join(ClassMember).filter(
        ClassMember.user_id == current_user.id
    ).all()
    
    # If no classes assigned, get all active classes (for admin)
    if not class_groups and current_user.role == 'admin':
        class_groups = ClassGroup.query.filter_by(is_active=True).all()
    
    # Get recent submissions
    recent_submissions = Submission.query.join(Assignment).filter(
        Assignment.class_group_id.in_([c.id for c in class_groups])
    ).order_by(Submission.submitted_at.desc()).limit(10).all()
    
    return render_template('teacher/dashboard.html', 
                         class_groups=class_groups, 
                         recent_submissions=recent_submissions)


@app.route('/teacher/classes')
@login_required
def manage_classes():
    """Manage class groups"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    if current_user.role == 'admin':
        class_groups = ClassGroup.query.all()
    else:
        class_groups = ClassGroup.query.join(ClassMember).filter(
            ClassMember.user_id == current_user.id
        ).all()
    
    return render_template('teacher/classes.html', class_groups=class_groups)


@app.route('/teacher/classes/create', methods=['GET', 'POST'])
@login_required
def create_class():
    """Create new class group"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        grade_level = request.form.get('grade_level', '').strip()
        academic_year = request.form.get('academic_year', '').strip()
        
        if not name:
            flash('Название класса обязательно', 'error')
            return render_template('teacher/class_form.html')
        
        class_group = ClassGroup(
            name=name,
            description=description,
            grade_level=grade_level,
            academic_year=academic_year
        )
        db.session.add(class_group)
        db.session.commit()
        
        # Add creator as member
        member = ClassMember(user_id=current_user.id, class_group_id=class_group.id, role='teacher')
        db.session.add(member)
        db.session.commit()
        
        flash('Класс успешно создан', 'success')
        return redirect(url_for('manage_classes'))
    
    return render_template('teacher/class_form.html')


@app.route('/teacher/topics')
@login_required
def manage_topics():
    """Manage topics"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    topics = Topic.query.filter_by(created_by=current_user.id).order_by(Topic.order_index).all()
    return render_template('teacher/topics.html', topics=topics)


@app.route('/teacher/topics/create', methods=['GET', 'POST'])
@login_required
def create_topic():
    """Create new topic"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#3B82F6')
        is_published = request.form.get('is_published') == 'on'
        
        if not title:
            flash('Название темы обязательно', 'error')
            return render_template('teacher/topic_form.html')
        
        topic = Topic(
            title=title,
            description=description,
            color=color,
            is_published=is_published,
            created_by=current_user.id
        )
        db.session.add(topic)
        db.session.commit()
        
        flash('Тема успешно создана', 'success')
        return redirect(url_for('manage_topics'))
    
    return render_template('teacher/topic_form.html')


@app.route('/teacher/topics/<int:topic_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_topic(topic_id):
    """Edit existing topic"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    topic = Topic.query.get_or_404(topic_id)
    
    if topic.created_by != current_user.id and current_user.role != 'admin':
        flash('У вас нет прав на редактирование этой темы', 'error')
        return redirect(url_for('manage_topics'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#3B82F6')
        is_published = request.form.get('is_published') == 'on'
        order_index = request.form.get('order_index', type=int) or 0
        
        if not title:
            flash('Название темы обязательно', 'error')
            return render_template('teacher/topic_form.html', topic=topic)
        
        topic.title = title
        topic.description = description
        topic.color = color
        topic.is_published = is_published
        topic.order_index = order_index
        topic.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Тема успешно обновлена', 'success')
        return redirect(url_for('manage_topics'))
    
    return render_template('teacher/topic_form.html', topic=topic)


@app.route('/teacher/topics/<int:topic_id>/delete', methods=['POST'])
@login_required
def delete_topic(topic_id):
    """Delete topic"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    topic = Topic.query.get_or_404(topic_id)
    
    if topic.created_by != current_user.id and current_user.role != 'admin':
        flash('У вас нет прав на удаление этой темы', 'error')
        return redirect(url_for('manage_topics'))
    
    # Check if topic has assignments
    if topic.assignments:
        flash('Нельзя удалить тему, содержащую задания. Сначала удалите или переместите задания.', 'error')
        return redirect(url_for('manage_topics'))
    
    db.session.delete(topic)
    db.session.commit()
    flash('Тема успешно удалена', 'success')
    return redirect(url_for('manage_topics'))


@app.route('/teacher/assignments')
@login_required
def manage_assignments():
    """Manage assignments"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    assignments = Assignment.query.filter_by(created_by=current_user.id).order_by(Assignment.created_at.desc()).all()
    return render_template('teacher/assignments.html', assignments=assignments)


@app.route('/teacher/assignments/create', methods=['GET', 'POST'])
@login_required
def create_assignment():
    """Create new assignment"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        topic_id = request.form.get('topic_id')
        class_group_id = request.form.get('class_group_id')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        starter_code = request.form.get('starter_code', '').strip()
        language = request.form.get('language', 'python')
        difficulty = request.form.get('difficulty', 'medium')
        assignment_type = request.form.get('assignment_type', 'practice')  # practice, independent, control
        duration_minutes = int(request.form.get('duration_minutes', 60))
        max_score = int(request.form.get('max_score', 100))
        is_published = request.form.get('is_published') == 'on'
        
        # Parse dates
        available_from = None
        available_until = None
        if request.form.get('available_from'):
            available_from = datetime.strptime(request.form.get('available_from'), '%Y-%m-%dT%H:%M')
        if request.form.get('available_until'):
            available_until = datetime.strptime(request.form.get('available_until'), '%Y-%m-%dT%H:%M')
        
        if not all([topic_id, class_group_id, title, description]):
            flash('Заполните все обязательные поля', 'error')
            topics = Topic.query.filter_by(created_by=current_user.id).all()
            class_groups = ClassGroup.query.join(ClassMember).filter(
                ClassMember.user_id == current_user.id
            ).all()
            if current_user.role == 'admin' and not class_groups:
                class_groups = ClassGroup.query.filter_by(is_active=True).all()
            return render_template('teacher/assignment_form.html', topics=topics, class_groups=class_groups)
        
        assignment = Assignment(
            topic_id=int(topic_id),
            class_group_id=int(class_group_id),
            title=title,
            description=description,
            starter_code=starter_code,
            language=language,
            difficulty=difficulty,
            assignment_type=assignment_type,
            duration_minutes=duration_minutes,
            max_score=max_score,
            available_from=available_from,
            available_until=available_until,
            is_published=is_published,
            visibility='published' if is_published else 'draft',
            created_by=current_user.id
        )
        db.session.add(assignment)
        db.session.commit()
        
        flash('Задание успешно создано', 'success')
        return redirect(url_for('manage_assignments'))
    
    # GET: show form
    topics = Topic.query.filter_by(created_by=current_user.id).all()
    class_groups = ClassGroup.query.join(ClassMember).filter(
        ClassMember.user_id == current_user.id
    ).all()
    
    if current_user.role == 'admin' and not class_groups:
        class_groups = ClassGroup.query.filter_by(is_active=True).all()
    
    return render_template('teacher/assignment_form.html', topics=topics, class_groups=class_groups, assignment_types=['practice', 'independent', 'control'])


@app.route('/teacher/assignments/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assignment(assignment_id):
    """Edit existing assignment"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if assignment.created_by != current_user.id and current_user.role != 'admin':
        flash('У вас нет прав на редактирование этого задания', 'error')
        return redirect(url_for('manage_assignments'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        topic_id = request.form.get('topic_id', type=int)
        class_group_id = request.form.get('class_group_id', type=int)
        starter_code = request.form.get('starter_code', '')
        language = request.form.get('language', 'python')
        difficulty = request.form.get('difficulty', 'medium')
        duration_minutes = request.form.get('duration_minutes', type=int) or 60
        max_score = request.form.get('max_score', type=int) or 100
        available_from_str = request.form.get('available_from', '')
        available_until_str = request.form.get('available_until', '')
        is_published = request.form.get('is_published') == 'on'
        
        if not title:
            flash('Название задания обязательно', 'error')
            return render_template('teacher/assignment_form.html', assignment=assignment, 
                                 topics=Topic.query.all(), 
                                 class_groups=ClassGroup.query.all())
        
        # Parse dates
        available_from = None
        available_until = None
        if available_from_str:
            try:
                available_from = datetime.strptime(available_from_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Неверный формат даты начала', 'error')
                return render_template('teacher/assignment_form.html', assignment=assignment,
                                     topics=Topic.query.all(),
                                     class_groups=ClassGroup.query.all())
        
        if available_until_str:
            try:
                available_until = datetime.strptime(available_until_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Неверный формат даты окончания', 'error')
                return render_template('teacher/assignment_form.html', assignment=assignment,
                                     topics=Topic.query.all(),
                                     class_groups=ClassGroup.query.all())
        
        # Update assignment
        assignment.title = title
        assignment.description = description
        assignment.topic_id = topic_id
        assignment.class_group_id = class_group_id
        assignment.starter_code = starter_code
        assignment.language = language
        assignment.difficulty = difficulty
        assignment.duration_minutes = duration_minutes
        assignment.max_score = max_score
        assignment.available_from = available_from
        assignment.available_until = available_until
        assignment.is_published = is_published
        assignment.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Задание успешно обновлено', 'success')
        return redirect(url_for('manage_assignments'))
    
    # GET: show form
    topics = Topic.query.all()
    class_groups = ClassGroup.query.all()
    return render_template('teacher/assignment_form.html', assignment=assignment, 
                         topics=topics, class_groups=class_groups)


@app.route('/teacher/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    """Delete assignment"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if assignment.created_by != current_user.id and current_user.role != 'admin':
        flash('У вас нет прав на удаление этого задания', 'error')
        return redirect(url_for('manage_assignments'))
    
    # Check if assignment has submissions
    if assignment.submissions:
        flash('Нельзя удалить задание с отправленными работами. Сначала удалите работы.', 'error')
        return redirect(url_for('manage_assignments'))
    
    db.session.delete(assignment)
    db.session.commit()
    flash('Задание успешно удалено', 'success')
    return redirect(url_for('manage_assignments'))


@app.route('/teacher/submissions')
@login_required
def review_submissions():
    """Review student submissions"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    # Get class IDs
    class_ids = [cm.class_group_id for cm in current_user.class_memberships]
    if current_user.role == 'admin':
        class_ids = [c.id for c in ClassGroup.query.all()]
    
    # Filter
    assignment_id = request.args.get('assignment_id', type=int)
    status = request.args.get('status', '')
    
    query = Submission.query.join(Assignment).filter(
        Assignment.class_group_id.in_(class_ids)
    )
    
    if assignment_id:
        query = query.filter(Submission.assignment_id == assignment_id)
    if status:
        query = query.filter(Submission.status == status)
    
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    
    return render_template('teacher/submissions.html', submissions=submissions)


@app.route('/teacher/submissions/<int:submission_id>/grade', methods=['GET', 'POST'])
@login_required
def grade_submission(submission_id):
    """Grade a submission"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    submission = Submission.query.get_or_404(submission_id)
    
    if request.method == 'POST':
        score = request.form.get('score', type=int)
        feedback = request.form.get('feedback', '').strip()
        status = 'graded'
        
        submission.score = score
        submission.feedback = feedback
        submission.status = status
        submission.graded_by = current_user.id
        submission.graded_at = datetime.utcnow()
        
        db.session.commit()
        log_activity('grade', {'score': score, 'feedback_length': len(feedback)}, submission.id)
        
        flash('Оценка выставлена', 'success')
        return redirect(url_for('review_submissions'))
    
    return render_template('teacher/grade_submission.html', submission=submission)


# ============== Admin Routes ==============

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard"""
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    stats = {
        'users': User.query.count(),
        'classes': ClassGroup.query.count(),
        'topics': Topic.query.count(),
        'assignments': Assignment.query.count(),
        'submissions': Submission.query.count()
    }
    
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/users')
@login_required
def manage_users():
    """Manage users"""
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


# ============== API Routes ==============

@app.route('/api/time')
@login_required
def get_server_time():
    """Get server time for timer synchronization"""
    return jsonify({
        'server_time': datetime.utcnow().isoformat(),
        'timezone': 'UTC'
    })


@app.route('/api/stats')
@login_required
def get_stats():
    """Get platform statistics"""
    if current_user.role == 'student':
        submissions = Submission.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            'total_submissions': len(submissions),
            'submitted': sum(1 for s in submissions if s.status == 'submitted'),
            'graded': sum(1 for s in submissions if s.status == 'graded'),
            'average_score': sum(s.score or 0 for s in submissions if s.score) / max(1, sum(1 for s in submissions if s.score))
        })
    elif current_user.role in ['teacher', 'admin']:
        return jsonify({
            'total_students': User.query.filter_by(role='student').count(),
            'total_assignments': Assignment.query.count(),
            'pending_submissions': Submission.query.filter_by(status='submitted').count()
        })
    
    return jsonify({}), 403


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


# ============== CSV Import/Export Routes ==============

@app.route('/teacher/students/import', methods=['GET', 'POST'])
@login_required
def import_students():
    """Import students from CSV file"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не загружен', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран', 'error')
            return redirect(request.url)

        if file and file.filename.endswith('.csv'):
            try:
                stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_reader = csv.DictReader(stream)
                
                imported_count = 0
                errors = []
                
                # Get or create class
                class_group_id = request.form.get('class_group_id', type=int)
                if not class_group_id:
                    flash('Выберите класс', 'error')
                    return redirect(request.url)
                
                class_group = ClassGroup.query.get_or_404(class_group_id)
                
                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        username = row.get('username', '').strip()
                        password = row.get('password', '').strip()
                        full_name = row.get('full_name', '').strip()
                        
                        if not username or not password:
                            errors.append(f"Строка {row_num}: отсутствуют username или password")
                            continue
                        
                        # Check if user exists
                        user = User.query.filter_by(username=username).first()
                        if user:
                            errors.append(f"Строка {row_num}: пользователь {username} уже существует")
                            continue
                        
                        # Create new student
                        student = User(
                            username=username,
                            full_name=full_name or username,
                            role='student',
                            is_active=True
                        )
                        student.set_password(password)
                        db.session.add(student)
                        db.session.flush()
                        
                        # Add to class
                        membership = ClassMember(user_id=student.id, class_group_id=class_group_id)
                        db.session.add(membership)
                        imported_count += 1
                    except Exception as e:
                        errors.append(f"Строка {row_num}: {str(e)}")
                
                db.session.commit()
                
                if imported_count > 0:
                    flash(f'Успешно импортировано {imported_count} учеников', 'success')
                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        flash(error, 'warning')
                    if len(errors) > 5:
                        flash(f'... и ещё {len(errors) - 5} ошибок', 'warning')
                
                return redirect(url_for('manage_class', class_id=class_group_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка импорта: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Загрузите файл в формате CSV', 'error')
            return redirect(request.url)

    # GET: show form
    class_groups = ClassGroup.query.join(ClassMember).filter(
        ClassMember.user_id == current_user.id
    ).all()
    if current_user.role == 'admin' and not class_groups:
        class_groups = ClassGroup.query.filter_by(is_active=True).all()
    
    return render_template('teacher/import_students.html', class_groups=class_groups)


@app.route('/teacher/students/export/<int:class_id>')
@login_required
def export_students(class_id):
    """Export students list to CSV"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    class_group = ClassGroup.query.get_or_404(class_id)
    
    # Check permission
    member_ids = [cm.class_group_id for cm in current_user.class_memberships]
    if current_user.role != 'admin' and class_id not in member_ids:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    # Get students
    members = ClassMember.query.filter_by(class_group_id=class_id).all()
    student_ids = [m.user_id for m in members]
    students = User.query.filter(User.id.in_(student_ids)).order_by(User.full_name).all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['username', 'password', 'full_name', 'email'])
    
    for student in students:
        # Password is placeholder since we can't retrieve hashed passwords
        writer.writerow([student.username, '********', student.full_name, student.email or ''])

    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'students_{class_group.name}_{datetime.now().strftime("%Y%m%d")}.csv'
    )


@app.route('/teacher/grades/export/<int:assignment_id>')
@login_required
def export_grades(assignment_id):
    """Export grades for assignment to CSV"""
    if current_user.role not in ['teacher', 'admin']:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check permission
    member_ids = [cm.class_group_id for cm in current_user.class_memberships]
    if current_user.role != 'admin' and assignment.class_group_id not in member_ids:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    # Get submissions
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    
    # Get activity logs for suspicious activity
    submission_ids = [s.id for s in submissions]
    activity_logs = {}
    if submission_ids:
        logs = ActivityLog.query.filter(
            ActivityLog.submission_id.in_(submission_ids),
            ActivityLog.event_type.in_(['tab_switch', 'blur', 'fullscreen_exit', 'devtools_attempt'])
        ).all()
        for log in logs:
            if log.submission_id not in activity_logs:
                activity_logs[log.submission_id] = []
            activity_logs[log.submission_id].append(log.event_type)

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'student_username', 'student_name', 'status', 'score', 'max_score', 
        'submitted_at', 'time_spent_minutes', 'suspicious_activity', 'feedback'
    ])
    
    for submission in submissions:
        student = submission.user
        suspicious = ', '.join(set(activity_logs.get(submission.id, []))) or 'None'
        time_spent = ''
        if submission.started_at and submission.submitted_at:
            delta = submission.submitted_at - submission.started_at
            time_spent = int(delta.total_seconds() / 60)
        
        writer.writerow([
            student.username,
            student.full_name,
            submission.status,
            submission.score or '',
            assignment.max_score,
            submission.submitted_at.strftime('%Y-%m-%d %H:%M') if submission.submitted_at else '',
            time_spent,
            suspicious,
            submission.feedback or ''
        ])

    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'grades_{assignment.title[:30]}_{datetime.now().strftime("%Y%m%d")}.csv'
    )



if __name__ == '__main__':
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Run app
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)


# Template context processors
@app.context_processor
def utility_processor():
    """Add utility functions to all templates"""
    def format_datetime(dt):
        if dt is None:
            return '—'
        return dt.strftime('%d.%m.%Y %H:%M')
    
    def format_date(dt):
        if dt is None:
            return '—'
        return dt.strftime('%d.%m.%Y')
    
    return {
        'formatDateTime': format_datetime,
        'formatDate': format_date
    }
