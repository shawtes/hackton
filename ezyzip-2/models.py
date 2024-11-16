from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_doctor = db.Column(db.Boolean, default=False)
    is_patient = db.Column(db.Boolean, default=False)
    
    # Additional patient fields
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    birth_date = db.Column(db.Date)
    insurance_number = db.Column(db.String(100), unique=True, nullable=True)

    # Define relationships
    participants = relationship('Participant', back_populates='user')
    messages = relationship('Message', back_populates='user')
    
    # Notes relationships - simplified
    written_notes = relationship('Note', 
                               foreign_keys='Note.doctor_id',
                               backref='doctor')
    received_notes = relationship('Note', 
                                foreign_keys='Note.patient_id',
                                backref='patient')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return True

class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    
    # Define relationships
    participants = relationship('Participant', back_populates='conversation')
    messages = relationship('Message', backref='conversation')

class Participant(db.Model):
    __tablename__ = 'participants'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'))
    
    # Define relationships
    user = relationship('User', back_populates='participants')
    conversation = relationship('Conversation', back_populates='participants')

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)

    # Define relationship
    user = relationship('User', back_populates='messages')

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)
    note_type = db.Column(db.String(50), nullable=False)  # 'soap', 'progress', 'prescription', 'lab', 'history'