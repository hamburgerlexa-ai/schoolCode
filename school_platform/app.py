from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from datetime import datetime
import json
import os
import sqlite3
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = 'school_platform_secret_key_2024_secure_random_string'

# Конфигурация
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'data', 'school.db')

def get_db():
    """Получить соединение с базой данных"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица заданий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            template_code TEXT NOT NULL,
            due_date DATE,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица отправок работ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            assignment_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            tab_switches INTEGER DEFAULT 0,
            time_spent INTEGER DEFAULT 0,
            suspicious_actions TEXT DEFAULT '[]',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id),
            UNIQUE(user_id, assignment_id)
        )
    ''')
    
    # Таблица логов подозрительной активности
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            assignment_id INTEGER,
            action_type TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')
    
    # Создаем учителя по умолчанию
    teacher_password = hashlib.sha256('admin123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, full_name, role)
        VALUES (?, ?, ?, ?)
    ''', ('teacher', teacher_password, 'Учитель Информатики', 'teacher'))
    
    # Создаем студентов по умолчанию
    students = [
        ('ivanov', '123', 'Иванов Иван'),
        ('petrov', '123', 'Петров Петр'),
        ('sidorov', '123', 'Сидоров Сидор'),
        ('smirnov', '123', 'Смирнов Алексей'),
        ('kozlov', '123', 'Козлов Дмитрий')
    ]
    
    for username, password, full_name in students:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, full_name, 'student'))
    
    # Создаем задания по умолчанию
    assignments = [
        ('Работа с циклами', 'Напишите программу, которая выводит все четные числа от 1 до 100', 
         '# Напишите ваш код здесь\ndef print_even_numbers():\n    # Ваш код\n    pass\n\nprint_even_numbers()', '2025-12-31'),
        ('Работа со строками', 'Напишите функцию, которая проверяет, является ли строка палиндромом',
         '# Напишите ваш код здесь\ndef is_palindrome(s):\n    # Ваш код\n    pass\n\nprint(is_palindrome("шалаш"))', '2025-12-31'),
        ('Работа со списками', 'Напишите функцию, которая находит максимальный элемент в списке',
         '# Напишите ваш код здесь\ndef find_max(lst):\n    # Ваш код\n    pass\n\nprint(find_max([1, 5, 3, 9, 2]))', '2025-12-31'),
        ('Работа с условиями', 'Напишите программу, которая определяет високосный ли год',
         '# Напишите ваш код здесь\ndef is_leap_year(year):\n    # Ваш код\n    pass\n\nprint(is_leap_year(2024))', '2025-12-31')
    ]
    
    for title, description, template_code, due_date in assignments:
        cursor.execute('''
            INSERT OR IGNORE INTO assignments (title, description, template_code, due_date)
            VALUES (?, ?, ?, ?)
        ''', (title, description, template_code, due_date))
    
    conn.commit()
    conn.close()

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """Декоратор для проверки прав учителя"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'teacher':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Декоратор для проверки прав студента"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role')
    
    if not username or not password:
        return render_template('login.html', error='Введите логин и пароль')
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, full_name, role FROM users
        WHERE username = ? AND password_hash = ? AND role = ?
    ''', (username, password_hash, role))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user['full_name']
        session['role'] = user['role']
        
        if role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    
    return render_template('login.html', error='Неверный логин, пароль или роль')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем все активные задания
    cursor.execute('SELECT * FROM assignments WHERE is_active = 1 ORDER BY created_at DESC')
    assignments = cursor.fetchall()
    
    # Получаем статус отправок для текущего студента
    cursor.execute('''
        SELECT assignment_id, submitted_at, tab_switches, time_spent, suspicious_actions
        FROM submissions WHERE user_id = ?
    ''', (session['user_id'],))
    submissions_data = {row['assignment_id']: dict(row) for row in cursor.fetchall()}
    
    conn.close()
    
    # Добавляем информацию о сдаче к каждому заданию
    for assignment in assignments:
        if assignment['id'] in submissions_data:
            assignment['submitted'] = True
            assignment['submission_info'] = submissions_data[assignment['id']]
        else:
            assignment['submitted'] = False
    
    return render_template('student_dashboard.html', 
                         name=session['full_name'],
                         assignments=assignments)

@app.route('/student/assignment/<int:assignment_id>')
@student_required
def student_assignment(assignment_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем задание
    cursor.execute('SELECT * FROM assignments WHERE id = ? AND is_active = 1', (assignment_id,))
    assignment = cursor.fetchone()
    
    if not assignment:
        conn.close()
        return redirect(url_for('student_dashboard'))
    
    # Получаем существующую отправку если есть
    cursor.execute('''
        SELECT code, tab_switches, time_spent, suspicious_actions
        FROM submissions WHERE user_id = ? AND assignment_id = ?
    ''', (session['user_id'], assignment_id))
    submission = cursor.fetchone()
    
    conn.close()
    
    existing_code = assignment['template_code']
    if submission:
        existing_code = submission['code']
    
    return render_template('assignment.html',
                         assignment=dict(assignment),
                         existing_code=existing_code,
                         student_name=session['full_name'])

@app.route('/student/submit/<int:assignment_id>', methods=['POST'])
@student_required
def submit_assignment(assignment_id):
    data = request.get_json()
    code = data.get('code', '')
    tab_switches = data.get('tab_switches', 0)
    time_spent = data.get('time_spent', 0)
    suspicious_actions = data.get('suspicious_actions', [])
    
    if not code.strip():
        return jsonify({'success': False, 'error': 'Код не может быть пустым'})
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Проверяем существование задания
    cursor.execute('SELECT id FROM assignments WHERE id = ?', (assignment_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Задание не найдено'})
    
    # Сохраняем или обновляем отправку
    cursor.execute('''
        INSERT INTO submissions (user_id, assignment_id, code, tab_switches, time_spent, suspicious_actions)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, assignment_id) DO UPDATE SET
            code = excluded.code,
            tab_switches = excluded.tab_switches,
            time_spent = excluded.time_spent,
            suspicious_actions = excluded.suspicious_actions,
            submitted_at = CURRENT_TIMESTAMP
    ''', (session['user_id'], assignment_id, code, int(tab_switches), int(time_spent), 
          json.dumps(suspicious_actions)))
    
    # Логируем подозрительную активность
    if tab_switches > 3 or len(suspicious_actions) > 0:
        cursor.execute('''
            INSERT INTO activity_logs (user_id, assignment_id, action_type, details)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], assignment_id, 'suspicious_activity',
              json.dumps({
                  'tab_switches': tab_switches,
                  'actions': suspicious_actions
              })))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Работа успешно сохранена'})

@app.route('/student/activity-log', methods=['POST'])
@student_required
def log_activity():
    """Эндпоинт для логирования активности ученика"""
    data = request.get_json()
    action_type = data.get('action_type')
    details = data.get('details', {})
    assignment_id = data.get('assignment_id')
    
    if action_type and assignment_id:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_logs (user_id, assignment_id, action_type, details)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], assignment_id, action_type, json.dumps(details)))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем все задания
    cursor.execute('SELECT * FROM assignments ORDER BY created_at DESC')
    assignments = cursor.fetchall()
    
    # Для каждого задания получаем статистику
    for i, assignment in enumerate(assignments):
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   AVG(tab_switches) as avg_switches,
                   COUNT(CASE WHEN tab_switches > 3 THEN 1 END) as suspicious_count
            FROM submissions WHERE assignment_id = ?
        ''', (assignment['id'],))
        stats = cursor.fetchone()
        assignments[i] = dict(assignment)
        assignments[i]['stats'] = dict(stats) if stats else {'total': 0, 'avg_switches': 0, 'suspicious_count': 0}
    
    # Получаем последние подозрительные активности
    cursor.execute('''
        SELECT al.*, u.full_name, a.title as assignment_title
        FROM activity_logs al
        JOIN users u ON al.user_id = u.id
        LEFT JOIN assignments a ON al.assignment_id = a.id
        WHERE al.action_type = 'suspicious_activity'
        ORDER BY al.timestamp DESC
        LIMIT 10
    ''')
    recent_alerts = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('teacher_dashboard.html',
                         assignments=assignments,
                         recent_alerts=recent_alerts,
                         teacher_name=session['full_name'])

@app.route('/teacher/assignment/<int:assignment_id>')
@teacher_required
def teacher_view_assignment(assignment_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем задание
    cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
    assignment = cursor.fetchone()
    
    if not assignment:
        conn.close()
        return redirect(url_for('teacher_dashboard'))
    
    # Получаем все отправки по этому заданию
    cursor.execute('''
        SELECT s.*, u.full_name, u.username
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        WHERE s.assignment_id = ?
        ORDER BY s.submitted_at DESC
    ''', (assignment_id,))
    submissions = [dict(row) for row in cursor.fetchall()]
    
    # Помечаем подозрительные отправки
    for sub in submissions:
        try:
            actions = json.loads(sub.get('suspicious_actions', '[]'))
        except:
            actions = []
        sub['is_suspicious'] = (sub['tab_switches'] > 3 or len(actions) > 0)
        sub['suspicious_details'] = actions
    
    conn.close()
    
    return render_template('teacher_view.html',
                         assignment=dict(assignment),
                         submissions=submissions)

@app.route('/teacher/submission/<int:submission_id>')
@teacher_required
def teacher_view_submission(submission_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.*, u.full_name, u.username, a.title as assignment_title
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        JOIN assignments a ON s.assignment_id = a.id
        WHERE s.id = ?
    ''', (submission_id,))
    submission = cursor.fetchone()
    
    conn.close()
    
    if not submission:
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('submission_detail.html', submission=dict(submission))

@app.route('/teacher/export/<int:assignment_id>')
@teacher_required
def export_submissions(assignment_id):
    """Экспорт всех отправок по заданию в JSON"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.*, u.full_name, u.username
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        WHERE s.assignment_id = ?
        ORDER BY u.username
    ''', (assignment_id,))
    
    submissions = []
    for row in cursor.fetchall():
        sub = dict(row)
        try:
            sub['suspicious_actions'] = json.loads(sub.get('suspicious_actions', '[]'))
        except:
            sub['suspicious_actions'] = []
        submissions.append(sub)
    
    conn.close()
    
    return jsonify({
        'assignment_id': assignment_id,
        'exported_at': datetime.now().isoformat(),
        'submissions': submissions
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
