"""
School Coding Platform - Database Models
Complete ORM models for users, classes, topics, assignments, submissions, and activity logs
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model with role-based access control"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # student, teacher, admin
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    avatar_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    class_memberships = db.relationship('ClassMember', back_populates='user', cascade='all, delete-orphan')
    submissions = db.relationship('Submission', foreign_keys='Submission.user_id', back_populates='user', cascade='all, delete-orphan')
    created_assignments = db.relationship('Assignment', foreign_keys='Assignment.created_by', back_populates='creator', cascade='all, delete-orphan')
    graded_submissions = db.relationship('Submission', foreign_keys='Submission.graded_by', back_populates='grader')
    activity_logs = db.relationship('ActivityLog', back_populates='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def __repr__(self):
        return f'<User {self.username}>'


class ClassGroup(db.Model):
    """Class/Group model for organizing students"""
    __tablename__ = 'class_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    grade_level = db.Column(db.String(20))
    academic_year = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('ClassMember', back_populates='class_group', cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', back_populates='class_group', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ClassGroup {self.name}>'


class ClassMember(db.Model):
    """Association table for users and class groups"""
    __tablename__ = 'class_members'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_group_id = db.Column(db.Integer, db.ForeignKey('class_groups.id'), nullable=False)
    role = db.Column(db.String(20), default='student')  # student, teacher_assistant
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='class_memberships')
    class_group = db.relationship('ClassGroup', back_populates='members')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'class_group_id', name='unique_class_member'),)
    
    def __repr__(self):
        return f'<ClassMember {self.user_id}:{self.class_group_id}>'


class Topic(db.Model):
    """Topic/Theme model for organizing assignments"""
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order_index = db.Column(db.Integer, default=0)
    color = db.Column(db.String(20), default='#3B82F6')  # Accent color for UI
    is_published = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignments = db.relationship('Assignment', back_populates='topic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<Topic {self.title}>'


class Assignment(db.Model):
    """Assignment model with full configuration options"""
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    class_group_id = db.Column(db.Integer, db.ForeignKey('class_groups.id'), nullable=True)  # Nullable for global assignments
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    starter_code = db.Column(db.Text)  # Template code for students
    language = db.Column(db.String(20), default='python')  # python, javascript, etc.
    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    assignment_type = db.Column(db.String(30), default='practice')  # practice, independent, control
    duration_minutes = db.Column(db.Integer, default=60)
    max_score = db.Column(db.Integer, default=100)
    
    # Timing
    available_from = db.Column(db.DateTime)
    available_until = db.Column(db.DateTime)
    auto_submit_enabled = db.Column(db.Boolean, default=True)
    
    # Visibility
    visibility = db.Column(db.String(20), default='draft')  # draft, published, archived
    is_published = db.Column(db.Boolean, default=False)
    
    # Test cases for auto-grading (JSON format)
    test_cases = db.Column(db.Text)  # JSON array of test cases
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    topic = db.relationship('Topic', back_populates='assignments')
    class_group = db.relationship('ClassGroup', back_populates='assignments')
    creator = db.relationship('User', foreign_keys=[created_by])
    submissions = db.relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')
    
    @property
    def is_available(self):
        now = datetime.utcnow()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return self.is_published
    
    def __repr__(self):
        return f'<Assignment {self.title}>'


class Submission(db.Model):
    """Student submission model with attempt tracking"""
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Content
    code = db.Column(db.Text)
    output = db.Column(db.Text)  # Program output
    error_message = db.Column(db.Text)  # Runtime errors
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, submitted, graded, expired, auto_submitted
    score = db.Column(db.Integer)
    max_score = db.Column(db.Integer)
    
    # Timing
    started_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    submitted_at = db.Column(db.DateTime)
    graded_at = db.Column(db.DateTime)
    
    # Grading
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    feedback = db.Column(db.Text)  # Teacher comments
    rubric_scores = db.Column(db.Text)  # JSON of rubric item scores
    
    # Anti-cheat metrics
    suspicion_score = db.Column(db.Integer, default=0)  # 0-100
    tab_switches = db.Column(db.Integer, default=0)
    fullscreen_exits = db.Column(db.Integer, default=0)
    devtools_attempts = db.Column(db.Integer, default=0)
    
    # Metadata
    attempt_number = db.Column(db.Integer, default=1)
    is_final = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignment = db.relationship('Assignment', back_populates='submissions')
    user = db.relationship('User', foreign_keys=[user_id], back_populates='submissions')
    grader = db.relationship('User', foreign_keys=[graded_by])
    activity_logs = db.relationship('ActivityLog', back_populates='submission', cascade='all, delete-orphan')
    grades = db.relationship('Grade', back_populates='submission', cascade='all, delete-orphan')
    
    @property
    def grade(self):
        """Convenience property to get the first grade for this submission"""
        return self.grades[0] if self.grades else None
    
    @property
    def is_expired(self):
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    @property
    def time_remaining(self):
        if self.expires_at:
            remaining = self.expires_at - datetime.utcnow()
            return max(0, int(remaining.total_seconds()))
        return None
    
    def __repr__(self):
        return f'<Submission {self.id} by {self.user_id}>'


class ActivityLog(db.Model):
    """Detailed activity logging for anti-cheat and analytics"""
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'))
    
    # Event type
    event_type = db.Column(db.String(50), nullable=False)  # tab_switch, fullscreen_exit, devtools_attempt, autosave, submit, etc.
    event_data = db.Column(db.Text)  # JSON additional data
    
    # Context
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    page_url = db.Column(db.String(500))
    
    # Timing
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', back_populates='activity_logs')
    submission = db.relationship('Submission', back_populates='activity_logs')
    
    def __repr__(self):
        return f'<ActivityLog {self.event_type} at {self.timestamp}>'


class Grade(db.Model):
    """Detailed grading with rubric support"""
    __tablename__ = 'grades'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    
    # Rubric item
    rubric_id = db.Column(db.Integer, db.ForeignKey('rubrics.id'))
    criterion_name = db.Column(db.String(200))
    points_earned = db.Column(db.Integer, nullable=False)
    points_possible = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    submission = db.relationship('Submission', back_populates='grades')
    rubric = db.relationship('Rubric', back_populates='grades')
    
    def __repr__(self):
        return f'<Grade {self.criterion_name}: {self.points_earned}/{self.points_possible}>'


class Rubric(db.Model):
    """Rubric criteria for grading assignments"""
    __tablename__ = 'rubrics'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    criterion_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    points_possible = db.Column(db.Integer, nullable=False, default=10)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    assignment = db.relationship('Assignment')
    grades = db.relationship('Grade', back_populates='rubric', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Rubric {self.criterion_name}>'


def init_db(app):
    """Initialize database with app context"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
