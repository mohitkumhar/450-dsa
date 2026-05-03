import json
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from mongoengine import connect, Document, StringField, IntField, BooleanField, ReferenceField, MapField, EmbeddedDocument, EmbeddedDocumentField
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')

# Connect to MongoDB
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/dsa_tracker')
connect(host=MONGO_URI)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

oauth = OAuth(app)

github = oauth.register(
    name='github',
    client_id=os.environ.get('GITHUB_CLIENT_ID', 'your-github-client-id'),
    client_secret=os.environ.get('GITHUB_CLIENT_SECRET', 'your-github-client-secret'),
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-client-secret'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

class ProgressItem(EmbeddedDocument):
    done = BooleanField(default=False)
    bookmark = BooleanField(default=False)
    notes = StringField(default="")

class User(Document, UserMixin):
    email = StringField(unique=True, sparse=True)
    password = StringField()
    name = StringField()
    github_id = StringField(unique=True, sparse=True)
    google_id = StringField(unique=True, sparse=True)
    progress = MapField(EmbeddedDocumentField(ProgressItem))

    def get_id(self):
        return str(self.id)

class Topic(Document):
    name = StringField(unique=True, required=True)
    position = IntField(required=True)

class Question(Document):
    topic = ReferenceField(Topic, reverse_delete_rule=2)
    problem = StringField(required=True)
    url = StringField(required=True)
    url2 = StringField()

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

def init_db():
    if Topic.objects.count() == 0:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            for t in data:
                topic = Topic(name=t['topicName'], position=t['position']).save()
                for q in t['questions']:
                    Question(
                        topic=topic,
                        problem=q['Problem'],
                        url=q['URL'],
                        url2=q.get('URL2', '')
                    ).save()

_db_initialized = False

@app.before_request
def before_request():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.objects(email=email).first()
        if user and user.password and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.objects(email=email).first()
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, password=hashed_password)
        try:
            user.save()
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('An error occurred during registration.', 'danger')
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/login/github')
def login_github():
    redirect_uri = url_for('authorize_github', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/login/github/authorize')
def authorize_github():
    token = github.authorize_access_token()
    resp = github.get('user')
    user_info = resp.json()
    github_id = str(user_info['id'])
    
    resp_emails = github.get('user/emails')
    email = None
    if resp_emails.status_code == 200:
        for e in resp_emails.json():
            if e['primary'] and e['verified']:
                email = e['email']
                break

    user = User.objects(github_id=github_id).first()
    if not user:
        if email:
            user = User.objects(email=email).first()
        if user:
            user.github_id = github_id
        else:
            user = User(name=user_info.get('name', user_info.get('login', 'GitHub User')), email=email, github_id=github_id)
        user.save()
    
    login_user(user)
    return redirect(url_for('index'))

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/authorize')
def authorize_google():
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token, nonce=session.get('nonce'))
    if not user_info:
        user_info = google.userinfo()
        
    google_id = user_info['sub']
    email = user_info.get('email')
    
    user = User.objects(google_id=google_id).first()
    if not user:
        if email:
            user = User.objects(email=email).first()
        if user:
            user.google_id = google_id
        else:
            user = User(name=user_info.get('name', 'Google User'), email=email, google_id=google_id)
        user.save()
        
    login_user(user)
    return redirect(url_for('index'))


@app.route('/')
def index():
    topics = Topic.objects.order_by('position')
    total_questions = Question.objects.count()
    
    if current_user.is_authenticated:
        user = current_user
        done_questions = sum(1 for p in user.progress.values() if p.done)
    else:
        done_questions = 0
    
    all_questions = Question.objects.all()
    topic_q_count = {}
    for q in all_questions:
        t_id = str(q.topic.id)
        topic_q_count[t_id] = topic_q_count.get(t_id, [])
        topic_q_count[t_id].append(str(q.id))
        
    topic_progress = {}
    for topic in topics:
        t_id = str(topic.id)
        t_q_ids = topic_q_count.get(t_id, [])
        if current_user.is_authenticated:
            t_done = sum(1 for q_id in t_q_ids if user.progress.get(q_id, ProgressItem()).done)
        else:
            t_done = 0
        topic_progress[t_id] = {
            'done': t_done,
            'total': len(t_q_ids)
        }
    
    return render_template('index.html', topics=topics, total_questions=total_questions, done_questions=done_questions, topic_progress=topic_progress)

@app.route('/topic/<topic_id>')
def topic(topic_id):
    topic = Topic.objects(id=topic_id).first()
    if not topic:
        return "Topic not found", 404
        
    questions = Question.objects(topic=topic)
    
    if current_user.is_authenticated:
        progress_dict = current_user.progress
    else:
        progress_dict = {}
    
    return render_template('topic.html', topic=topic, questions=questions, progress_dict=progress_dict)

@app.route('/update_question/<question_id>', methods=['POST'])
@login_required
def update_question(question_id):
    question = Question.objects(id=question_id).first()
    if not question:
        return jsonify({"success": False, "error": "Question not found"}), 404
        
    data = request.json
    
    if question_id not in current_user.progress:
        current_user.progress[question_id] = ProgressItem()
        
    if 'done' in data:
        current_user.progress[question_id].done = data['done']
    if 'bookmark' in data:
        current_user.progress[question_id].bookmark = data['bookmark']
    if 'notes' in data:
        current_user.progress[question_id].notes = data['notes']
        
    current_user.save()
    
    return jsonify({"success": True})

@app.route('/bookmarks')
@login_required
def bookmarks():
    user = current_user
    bookmarked_q_ids = [q_id for q_id, p in user.progress.items() if p.bookmark]
    
    questions = Question.objects(id__in=bookmarked_q_ids)
    progress_dict = user.progress
    
    return render_template('bookmarks.html', questions=questions, progress_dict=progress_dict)

if __name__ == '__main__':
    app.run(debug=True)
