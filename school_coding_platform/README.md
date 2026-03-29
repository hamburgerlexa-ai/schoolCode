# School Coding Platform

Полноценная образовательная платформа для проверки заданий по программированию с системой античитинга.

## Возможности

### Для учителей:
- ✅ Создание и управление классами
- ✅ Создание тем и заданий
- ✅ Настройка времени выполнения и дедлайнов
- ✅ Проверка работ учеников
- ✅ Выставление оценок и комментариев
- ✅ Мониторинг подозрительной активности
- ✅ Просмотр статистики по классу

### Для учеников:
- ✅ Просмотр доступных заданий
- ✅ Редактор кода с подсветкой синтаксиса
- ✅ Таймер обратного отсчёта
- ✅ Автосохранение черновиков (каждые 30 сек)
- ✅ Отправка работ на проверку
- ✅ Просмотр результатов и комментариев учителя

### Система античитинга:
- 🛡️ Детекция переключения вкладок
- 🛡️ Мониторинг выхода из fullscreen
- 🛡️ Обнаружение попыток открытия DevTools
- 🛡️ Подсчёт уровня подозрительности (0-100%)
- 🛡️ Полное логирование активности

## Технологии

**Backend:**
- Flask 3.0 + SQLAlchemy
- Flask-Login (аутентификация)
- Flask-WTF (CSRF защита)
- werkzeug.security (хеширование паролей bcrypt)

**Frontend:**
- Premium тёмный дизайн (Linear/Stripe style)
- CodeMirror (редактор кода)
- Font Awesome (иконки)
- Inter шрифт

**Database:**
- SQLite (для демонстрации)
- Поддержка PostgreSQL/MySQL через SQLAlchemy

## Быстрый старт

### Установка зависимостей

```bash
cd school_coding_platform
pip install -r requirements.txt
```

### Конфигурация

```bash
cp .env.example .env
# Отредактируйте .env при необходимости
```

### Инициализация БД и демо-данных

```bash
python << 'EOF'
from app import app, db
from models import User, ClassGroup, Topic, ClassMember, Assignment
from datetime import datetime, timedelta

with app.app_context():
    db.create_all()
    
    # Создаём пользователей
    admin = User(username='admin', email='admin@school.com', role='admin')
    admin.set_password('admin123')
    db.session.add(admin)
    
    teacher = User(username='teacher', email='teacher@school.com', role='teacher')
    teacher.set_password('teacher123')
    db.session.add(teacher)
    
    student = User(username='student', email='student@school.com', role='student')
    student.set_password('student123')
    db.session.add(student)
    
    db.session.flush()
    
    # Класс
    class_group = ClassGroup(name='10A Класс')
    db.session.add(class_group)
    db.session.flush()
    
    db.session.add(ClassMember(user_id=teacher.id, class_group_id=class_group.id, role='teacher'))
    db.session.add(ClassMember(user_id=student.id, class_group_id=class_group.id, role='student'))
    
    # Тема
    topic = Topic(title='Введение в Python', is_published=True, created_by=teacher.id)
    db.session.add(topic)
    db.session.flush()
    
    # Задание
    assignment = Assignment(
        topic_id=topic.id,
        class_group_id=class_group.id,
        title='Hello, World!',
        description='<h3>Задание</h3><p>Напишите программу, выводящую "Hello, World!"</p>',
        starter_code='# Ваш код здесь\n',
        duration_minutes=30,
        is_published=True,
        available_until=datetime.utcnow() + timedelta(days=7),
        created_by=teacher.id
    )
    db.session.add(assignment)
    db.session.commit()
    
print('Готово! Данные для входа:')
print('  Admin:   admin / admin123')
print('  Teacher: teacher / teacher123')
print('  Student: student / student123')
EOF
```

### Запуск сервера

```bash
python app.py
```

Сервер запустится на `http://localhost:5000`

## Демо-доступы

| Роль | Логин | Пароль |
|------|-------|--------|
| Администратор | admin | admin123 |
| Учитель | teacher | teacher123 |
| Ученик | student | student123 |

## Структура проекта

```
school_coding_platform/
├── app.py                 # Основное приложение Flask
├── models.py              # ORM модели (8 таблиц)
├── requirements.txt       # Зависимости Python
├── .env                   # Конфигурация
├── templates/             # HTML шаблоны
│   ├── base.html         # Базовый шаблон
│   ├── login.html        # Страница входа
│   ├── register.html     # Регистрация
│   ├── student/          # Шаблоны ученика
│   │   ├── dashboard.html
│   │   ├── assignment.html
│   │   └── submission_review.html
│   └── teacher/          # Шаблоны учителя
├── static/               # Статические файлы
│   ├── css/
│   └── js/
└── instance/
    └── school_platform.db # База данных SQLite
```

## Модели данных

- **User** - Пользователи (ученики, учителя, админы)
- **ClassGroup** - Классы/группы
- **ClassMember** - Членство в классах
- **Topic** - Темы занятий
- **Assignment** - Задания
- **Submission** - Работы учеников
- **ActivityLog** - Логи активности
- **Grade** - Оценки
- **Rubric** - Критерии оценивания

## API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/submission/<id>/autosave` | Автосохранение черновика |
| POST | `/api/submission/<id>/activity` | Логирование активности |
| GET | `/api/time` | Серверное время |
| GET | `/api/stats` | Статистика пользователя |

## Безопасность

- ✅ Хеширование паролей (pbkdf2:sha256)
- ✅ CSRF защита всех форм
- ✅ Ролевая модель доступа
- ✅ Валидация данных на сервере
- ✅ Защита от XSS атак

## Roadmap

- [ ] Автопроверка кода через тесты
- [ ] Песочница для безопасного запуска кода
- [ ] Экспорт работ в PDF/CSV
- [ ] Уведомления (email, Telegram)
- [ ] Мобильное приложение
- [ ] Интеграция с GitHub Classroom

## Лицензия

MIT License

---

**School Coding Platform** © 2024 - Образовательная платформа нового поколения
