import json
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dsa.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    started = db.Column(db.Boolean, default=False)
    questions = db.relationship('Question', backref='topic', lazy=True)

    @property
    def done_questions(self):
        return sum(1 for q in self.questions if q.done)

    @property
    def total_questions(self):
        return len(self.questions)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    problem = db.Column(db.String(300), nullable=False)
    done = db.Column(db.Boolean, default=False)
    bookmark = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, default="")
    url = db.Column(db.String(500), nullable=False)
    url2 = db.Column(db.String(500), nullable=True)

def init_db():
    if not os.path.exists('instance'):
        os.makedirs('instance')
    if not os.path.exists('instance/dsa.db'):
        with app.app_context():
            db.create_all()
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                for t in data:
                    topic = Topic(name=t['topicName'], position=t['position'], started=t.get('started', False))
                    db.session.add(topic)
                    db.session.commit()
                    for q in t['questions']:
                        question = Question(
                            topic_id=topic.id,
                            problem=q['Problem'],
                            done=q.get('Done', False),
                            bookmark=q.get('Bookmark', False),
                            notes=q.get('Notes', ''),
                            url=q['URL'],
                            url2=q.get('URL2', '')
                        )
                        db.session.add(question)
                    db.session.commit()

@app.before_request
def before_request():
    init_db()

@app.route('/')
def index():
    topics = Topic.query.order_by(Topic.position).all()
    total_questions = Question.query.count()
    done_questions = Question.query.filter_by(done=True).count()
    return render_template('index.html', topics=topics, total_questions=total_questions, done_questions=done_questions)

@app.route('/topic/<int:topic_id>')
def topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    return render_template('topic.html', topic=topic)

@app.route('/update_question/<int:question_id>', methods=['POST'])
def update_question(question_id):
    question = Question.query.get_or_404(question_id)
    data = request.json
    
    if 'done' in data:
        question.done = data['done']
    if 'bookmark' in data:
        question.bookmark = data['bookmark']
    if 'notes' in data:
        question.notes = data['notes']
        
    db.session.commit()
    
    # Update topic 'started' status
    topic = question.topic
    if any(q.done for q in topic.questions):
        topic.started = True
    else:
        topic.started = False
    db.session.commit()
    
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)
