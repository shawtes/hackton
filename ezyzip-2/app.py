from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Message, Conversation, Participant, Note
import firebase_admin
from firebase_admin import credentials, db as firebase_db
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///telehealth.db'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Firebase Admin SDK
cred = credentials.Certificate('/Users/sineshawmesfintesfaye/Downloads/okkk-15588-firebase-adminsdk-8i3zi-e35fbbf8da.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://okkk-15588-default-rtdb.firebaseio.com'
})

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # Updated to avoid deprecation warning

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/chat')
@login_required
def chat():
    if current_user.is_doctor:
        # Doctors see list of patients
        patients = User.query.filter_by(is_patient=True).all()
        conversations = Conversation.query.join(Participant).filter(Participant.user_id == current_user.id).all()
        return render_template('chat.html', users=patients, conversations=conversations)
    elif current_user.is_patient:
        # Patients see their conversations with doctors
        conversations = Conversation.query.join(Participant).filter(Participant.user_id == current_user.id).all()
        doctors = User.query.filter_by(is_doctor=True).all()
        return render_template('chat.html', users=doctors, conversations=conversations)
    else:
        flash('Unauthorized access')
        return redirect(url_for('home'))

@app.route('/notes', methods=['GET', 'POST'])
@login_required
def notes():
    if current_user.is_doctor:
        patients = User.query.filter_by(is_patient=True).all()
        # Get all notes written by this doctor
        notes = Note.query.filter_by(doctor_id=current_user.id).order_by(Note.timestamp.desc()).all()
        # Parse JSON content for each note
        for note in notes:
            try:
                note.content = json.loads(note.content)
            except:
                note.content = {}
        return render_template('notes.html', patients=patients, notes=notes)
    elif current_user.is_patient:
        # For patients viewing their own notes
        notes = Note.query.filter_by(patient_id=current_user.id).order_by(Note.timestamp.desc()).all()
        # Parse JSON content for each note
        for note in notes:
            try:
                note.content = json.loads(note.content)
            except:
                note.content = {}
        return render_template('notes.html', notes=notes)
    else:
        flash('Unauthorized access')
        return redirect(url_for('home'))

@app.route('/video-call')
@login_required
def video_call():
    return render_template('video_call.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        account_type = request.form['account_type']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username)
        new_user.set_password(password)
        if account_type == 'doctor':
            new_user.is_doctor = True
        else:
            new_user.is_patient = True
        
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/start_conversation/<int:recipient_id>', methods=['POST'])
@login_required
def start_conversation(recipient_id):
    # Verify that current user is a doctor and recipient is a patient
    recipient = User.query.get(recipient_id)
    if not current_user.is_doctor or not recipient.is_patient:
        return jsonify({'error': 'Invalid conversation participants'}), 403
    
    # Check if conversation already exists between these users
    existing_conversation = Conversation.query.join(Participant).filter(
        Participant.user_id.in_([current_user.id, recipient_id])
    ).group_by(Conversation.id).having(db.func.count(Participant.id) == 2).first()
    
    if existing_conversation:
        conversation_id = existing_conversation.id
    else:
        # Create new conversation
        new_conversation = Conversation(name=f"Consultation: Dr. {current_user.username} with {recipient.username}")
        db.session.add(new_conversation)
        db.session.commit()
        
        # Add participants
        participant1 = Participant(user_id=current_user.id, conversation_id=new_conversation.id)
        participant2 = Participant(user_id=recipient_id, conversation_id=new_conversation.id)
        db.session.add(participant1)
        db.session.add(participant2)
        db.session.commit()
        conversation_id = new_conversation.id
    
    return jsonify({'conversation_id': conversation_id})

@app.route('/save_note', methods=['POST'])
@login_required
def save_note():
    if not current_user.is_doctor:
        return jsonify({'error': 'Only doctors can create notes'}), 403
    
    try:
        data = request.json
        patient_id = data.get('patient_id')
        note_type = data.get('note_type')
        content = data.get('content')
        
        # Create a structured content based on note type
        formatted_content = {}
        if note_type == 'soap':
            formatted_content = {
                'subjective': content.get('subjective', ''),
                'objective': content.get('objective', ''),
                'assessment': content.get('assessment', ''),
                'plan': content.get('plan', '')
            }
        elif note_type == 'progress':
            formatted_content = {
                'progress': content.get('progress', ''),
                'treatment': content.get('treatment', '')
            }
        elif note_type == 'prescription':
            formatted_content = {
                'medication': content.get('medication', ''),
                'dosage': content.get('dosage', ''),
                'frequency': content.get('frequency', ''),
                'duration': content.get('duration', ''),
                'instructions': content.get('instructions', '')
            }
        elif note_type == 'lab':
            formatted_content = {
                'lab_results': content.get('lab_results', ''),
                'interpretation': content.get('interpretation', '')
            }
        elif note_type == 'history':
            formatted_content = {
                'medical_history': content.get('medical_history', ''),
                'family_history': content.get('family_history', ''),
                'social_history': content.get('social_history', '')
            }
        
        note = Note(
            content=json.dumps(formatted_content),
            doctor_id=current_user.id,
            patient_id=patient_id,
            note_type=note_type
        )
        
        db.session.add(note)
        db.session.commit()
        
        return jsonify({
            'message': 'Note saved successfully',
            'note_id': note.id,
            'timestamp': note.timestamp.isoformat()
        })
        
    except Exception as e:
        print(f"Error saving note: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to save note'}), 500

@app.route('/get_notes/<int:patient_id>')
@login_required
def get_notes(patient_id):
    if not current_user.is_doctor and current_user.id != patient_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    notes = Note.query.filter_by(patient_id=patient_id).order_by(Note.timestamp.desc()).all()
    return jsonify([{
        'id': note.id,
        'content': json.loads(note.content),
        'note_type': note.note_type,
        'timestamp': note.timestamp.isoformat(),
        'doctor_name': User.query.get(note.doctor_id).username
    } for note in notes])

@app.route('/get_notes_by_type/<int:patient_id>/<note_type>')
@login_required
def get_notes_by_type(patient_id, note_type):
    if not current_user.is_doctor and current_user.id != patient_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    notes = Note.query.filter_by(
        patient_id=patient_id,
        note_type=note_type
    ).order_by(Note.timestamp.desc()).all()
    
    return jsonify([{
        'id': note.id,
        'content': json.loads(note.content),
        'note_type': note_type,
        'timestamp': note.timestamp.isoformat(),
        'doctor_name': User.query.get(note.doctor_id).username
    } for note in notes])

@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except:
        return {}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)