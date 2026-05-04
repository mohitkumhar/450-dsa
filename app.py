import json
import os
import re
import requests
import base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from mongoengine import connect, Document, StringField, IntField, BooleanField, ReferenceField, MapField, EmbeddedDocument, EmbeddedDocumentField, DateTimeField, ListField
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
    timestamp = DateTimeField(default=datetime.utcnow)

class User(Document, UserMixin):
    email = StringField(unique=True, sparse=True)
    password = StringField()
    name = StringField()
    github_id = StringField(unique=True, sparse=True)
    google_id = StringField(unique=True, sparse=True)
    progress = MapField(EmbeddedDocumentField(ProgressItem))
    leetcode_username = StringField()
    github_username = StringField()
    gfg_username = StringField()
    external_daily_counts = MapField(IntField())
    external_totals = MapField(IntField())
    # Profile fields
    bio = StringField(default='')
    location = StringField(default='')
    college = StringField(default='')
    headline = StringField(default='')
    linkedin_url = StringField(default='')
    twitter_url = StringField(default='')
    website_url = StringField(default='')
    resume_url = StringField(default='')
    profile_photo = StringField(default='')  # base64 data URL or external URL
    rating_history = ListField(default=list)  # [{x: date, y: rating}]
    lc_badges_json = StringField(default='[]')
    hr_badges_json = StringField(default='[]')

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

def fetch_leetcode(username):
    try:
        r = requests.post("https://leetcode.com/graphql", json={
            "query": f'{{ matchedUser(username: "{username}") {{ submitStatsGlobal {{ acSubmissionNum {{ difficulty count }} }} userCalendar {{ submissionCalendar }} }} userContestRanking(username: "{username}") {{ attendedContestsCount rating globalRanking topPercentage }} }}'
        }, timeout=8)
        resp_json = r.json().get('data', {})
        data = resp_json.get('matchedUser', {})
        if not data: return {}
        cal_str = data.get('userCalendar', {}).get('submissionCalendar', '{}')
        cal_data = json.loads(cal_str) if cal_str else {}
        res_cal = {}
        for ts, count in cal_data.items():
            dt = datetime.utcfromtimestamp(int(ts)).strftime('%Y-%m-%d')
            res_cal[dt] = res_cal.get(dt, 0) + count
        total_solved = 0
        diff_stats = {'Easy': 0, 'Medium': 0, 'Hard': 0}
        stats = data.get('submitStatsGlobal', {}).get('acSubmissionNum', [])
        for stat in stats:
            diff = stat.get('difficulty')
            if diff == 'All': total_solved = stat.get('count', 0)
            elif diff in diff_stats: diff_stats[diff] = stat.get('count', 0)
        contest = resp_json.get('userContestRanking', {})
        return {"calendar": res_cal, "total": total_solved, "difficulty": diff_stats, "contest": contest}
    except Exception as e:
        print("LC Error", e)
        return {}

def fetch_leetcode_rating_history(username):
    """Fetch contest rating history for the rating graph."""
    try:
        query = '''
        query userContestRankingInfo($username: String!) {
          userContestRankingHistory(username: $username) {
            attended
            rating
            contest { title startTime }
          }
        }'''
        r = requests.post("https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            timeout=10,
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"})
        history_raw = r.json().get('data', {}).get('userContestRankingHistory', [])
        result = []
        for item in history_raw:
            if item.get('attended'):
                ts = item.get('contest', {}).get('startTime', 0)
                dt = datetime.utcfromtimestamp(int(ts)).strftime('%Y-%m-%d')
                result.append({'x': dt, 'y': round(float(item.get('rating', 0)), 0)})
        return sorted(result, key=lambda x: x['x'])
    except Exception as e:
        print("LC Rating History Error", e)
        return []

def fetch_lc_badges(username):
    """Fetch LeetCode badges/awards for the user."""
    try:
        query = '''
        query userBadges($username: String!) {
          matchedUser(username: $username) {
            badges { id displayName icon }
            upcomingBadges { name icon }
          }
        }'''
        r = requests.post("https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            timeout=8,
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"})
        badges_raw = r.json().get('data', {}).get('matchedUser', {}).get('badges', [])
        return [{'name': b['displayName'], 'icon': ('https://leetcode.com' + b['icon'] if b.get('icon', '').startswith('/') else b.get('icon', ''))} for b in badges_raw]
    except Exception as e:
        print("LC Badges Error", e)
        return []

def fetch_hr_badges(username):
    """Fetch HackerRank badges for the user."""
    try:
        r = requests.get(f"https://www.hackerrank.com/rest/hackers/{username}/badges",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json().get('models', [])
            return [{'name': b.get('badge_name', ''), 'stars': b.get('stars', 0)} for b in data if b.get('badge_name')]
        return []
    except Exception as e:
        print("HR Badges Error", e)
        return []

def fetch_github(username):
    try:
        r = requests.get(f"https://github.com/users/{username}/contributions", timeout=5)
        matches = re.findall(r'(\d+|No)\s+contributions?\s+on\s+(\d{4}-\d{2}-\d{2})', r.text)
        res_cal = {}
        for count_str, date_str in matches:
            count = 0 if count_str == 'No' else int(count_str)
            res_cal[date_str] = count
            
        res_issues = requests.get(f"https://api.github.com/search/issues?q=type:issue+author:{username}", timeout=5).json()
        res_prs = requests.get(f"https://api.github.com/search/issues?q=type:pr+author:{username}", timeout=5).json()
        res_merged = requests.get(f"https://api.github.com/search/issues?q=type:pr+is:merged+author:{username}", timeout=5).json()
        headers = {"Accept": "application/vnd.github.cloak-preview+json"}
        res_commits = requests.get(f"https://api.github.com/search/commits?q=author:{username}", headers=headers, timeout=5).json()
        
        stats = {
            "issues": res_issues.get('total_count', 0),
            "prs": res_prs.get('total_count', 0),
            "merged_prs": res_merged.get('total_count', 0),
            "commits": res_commits.get('total_count', 0)
        }
            
        return {"calendar": res_cal, "stats": stats}
    except Exception as e:
        print("GH Error", e)
        return {}

def fetch_gfg(username):
    """Fetch GFG solved count via multiple fallback methods."""
    try:
        # Method 1: Unofficial stats API
        try:
            r = requests.get(f"https://geeks-for-geeks-stats-api.vercel.app/?raw=Y&userName={username}", timeout=6)
            if r.status_code == 200:
                d = r.json()
                total = d.get('totalProblemsSolved') or d.get('total_problems_solved', 0)
                if total and int(total) > 0:
                    return {"total": int(total)}
        except: pass
        # Method 2: GFG practice API
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r2 = requests.get(f"https://practiceapi.geeksforgeeks.org/api/v1/user/practice/stats/?user={username}",
                              headers=headers, timeout=6)
            if r2.status_code == 200:
                d2 = r2.json()
                total = d2.get('data', {}).get('total_problems_solved', 0)
                if total: return {"total": int(total)}
        except: pass
        # Method 3: Scrape profile page
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}
        r3 = requests.get(f"https://www.geeksforgeeks.org/user/{username}/", timeout=8, headers=headers)
        for pattern in [
            r'"total_problems_solved"\s*[:=]\s*(\d+)',
            r'"totalProblemsSolved"\s*[:=]\s*(\d+)',
            r'total_problems_solved.*?(\d+)',
            r'Problems Solved[^\d]*(\d+)',
            r'class="score_card_value"[^>]*>(\d+)<',
        ]:
            m = re.search(pattern, r3.text, re.IGNORECASE)
            if m:
                return {"total": int(m.group(1))}
        return {"total": 0}
    except Exception as e:
        print("GFG Error", e)
        return {}

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


@app.template_filter('platform_name')
def platform_name_filter(url):
    if not url: return None
    url = url.lower()
    if 'leetcode.com' in url: return 'LeetCode'
    if 'geeksforgeeks.org' in url: return 'GFG'
    if 'codingninjas.com' in url: return 'Coding Ninjas'
    if 'youtube.com' in url or 'youtu.be' in url: return 'YouTube'
    if 'hackerrank.com' in url: return 'HackerRank'
    return 'Link'

@app.template_filter('platform_color')
def platform_color_filter(name):
    colors = {
        'LeetCode': 'warning text-dark',
        'GFG': 'success',
        'Coding Ninjas': 'danger',
        'YouTube': 'danger',
        'HackerRank': 'success'
    }
    return colors.get(name, 'primary')

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
        if data['done'] and not current_user.progress[question_id].done:
            current_user.progress[question_id].timestamp = datetime.utcnow()
        current_user.progress[question_id].done = data['done']
    if 'bookmark' in data:
        current_user.progress[question_id].bookmark = data['bookmark']
    if 'notes' in data:
        current_user.progress[question_id].notes = data['notes']
        
    current_user.save()
    
    return jsonify({"success": True})

@app.route('/sync_platforms', methods=['POST'])
@login_required
def sync_platforms():
    data = request.json
    current_user.leetcode_username = data.get('leetcode', '').strip()
    current_user.github_username = data.get('github', '').strip()
    current_user.gfg_username = data.get('gfg', '').strip()
    combined = {}
    totals = {}
    if current_user.leetcode_username:
        lc = fetch_leetcode(current_user.leetcode_username)
        for k, v in lc.get('calendar', {}).items(): combined[k] = combined.get(k, 0) + v
        if lc.get('total'): totals['LeetCode'] = lc.get('total')
        if lc.get('difficulty'):
            totals['LeetCode_Easy'] = lc['difficulty'].get('Easy', 0)
            totals['LeetCode_Medium'] = lc['difficulty'].get('Medium', 0)
            totals['LeetCode_Hard'] = lc['difficulty'].get('Hard', 0)
        if lc.get('contest'):
            totals['LeetCode_Contests'] = lc['contest'].get('attendedContestsCount', 0)
            totals['LeetCode_Rating'] = int(lc['contest'].get('rating', 0))
            totals['LeetCode_GlobalRank'] = lc['contest'].get('globalRanking', 0)
        # Fetch rating history for graph
        rh = fetch_leetcode_rating_history(current_user.leetcode_username)
        if rh: current_user.rating_history = rh
        # Fetch LC badges and store in dedicated field
        lc_badges = fetch_lc_badges(current_user.leetcode_username)
        current_user.lc_badges_json = json.dumps(lc_badges)
    if current_user.github_username:
        gh = fetch_github(current_user.github_username)
        for k, v in gh.get('calendar', {}).items(): combined[k] = combined.get(k, 0) + v
        if gh.get('stats'):
            totals['GitHub_Issues'] = gh['stats']['issues']
            totals['GitHub_PRs'] = gh['stats']['prs']
            totals['GitHub_Merged_PRs'] = gh['stats']['merged_prs']
            totals['GitHub_Commits'] = gh['stats']['commits']
    if current_user.gfg_username:
        gfg = fetch_gfg(current_user.gfg_username)
        if gfg.get('total'): totals['GFG'] = int(gfg.get('total', 0))
    # HackerRank badges stored in dedicated field
    if current_user.gfg_username:
        try:
            hr_badges = fetch_hr_badges(current_user.gfg_username)
            current_user.hr_badges_json = json.dumps(hr_badges)
        except: pass
    current_user.external_daily_counts = combined
    current_user.external_totals = totals
    current_user.save()
    return jsonify({"success": True})

@app.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    # Text fields
    for field in ['name','bio','location','college','headline','linkedin_url','twitter_url','website_url','resume_url']:
        if field in data:
            setattr(current_user, field, data[field].strip())
    current_user.save()
    return jsonify({"success": True})

@app.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({"success": False, "error": "No file"}), 400
    f = request.files['photo']
    if f.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    allowed = {'png','jpg','jpeg','gif','webp'}
    ext = f.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({"success": False, "error": "Invalid file type"}), 400
    raw = f.read()
    if len(raw) > 2 * 1024 * 1024:  # 2MB limit
        return jsonify({"success": False, "error": "File too large (max 2MB)"}), 400
    b64 = base64.b64encode(raw).decode('utf-8')
    mime = f'image/{ext}'
    current_user.profile_photo = f'data:{mime};base64,{b64}'
    current_user.save()
    return jsonify({"success": True, "photo_url": current_user.profile_photo})

@app.route('/bookmarks')
@login_required
def bookmarks():
    user = current_user
    bookmarked_q_ids = [q_id for q_id, p in user.progress.items() if p.bookmark]
    
    questions = Question.objects(id__in=bookmarked_q_ids)
    progress_dict = user.progress
    
    return render_template('bookmarks.html', questions=questions, progress_dict=progress_dict)

@app.route('/profile')
@login_required
def profile():
    topics = Topic.objects.order_by('position')
    user = current_user
    
    all_questions = Question.objects.all()
    solved_items = {q_id: p for q_id, p in user.progress.items() if p.done}
    
    platforms = {'LeetCode': 0, 'GFG': 0, 'Coding Ninjas': 0, 'HackerRank': 0, 'Other': 0}
    daily_counts = {}
    
    topic_q_count = {}
    for q in all_questions:
        t_id = str(q.topic.id)
        topic_q_count[t_id] = topic_q_count.get(t_id, [])
        topic_q_count[t_id].append(str(q.id))
        
        q_id = str(q.id)
        if q_id in solved_items:
            url = (q.url or "").lower()
            if 'leetcode.com' in url: platforms['LeetCode'] += 1
            elif 'geeksforgeeks.org' in url: platforms['GFG'] += 1
            elif 'codingninjas.com' in url: platforms['Coding Ninjas'] += 1
            elif 'hackerrank.com' in url: platforms['HackerRank'] += 1
            else: platforms['Other'] += 1
            
            dt = getattr(solved_items[q_id], 'timestamp', None)
            if not dt:
                dt = datetime.utcnow()
            d_str = dt.strftime('%Y-%m-%d')
            daily_counts[d_str] = daily_counts.get(d_str, 0) + 1
            
    # Merge external counts
    if hasattr(user, 'external_daily_counts') and user.external_daily_counts:
        for d_str, count in user.external_daily_counts.items():
            daily_counts[d_str] = daily_counts.get(d_str, 0) + count

    total_active_days = len(daily_counts)
    sorted_dates = sorted(daily_counts.keys())
    cumulative_data = []
    cum_sum = 0
    for d in sorted_dates:
        cum_sum += daily_counts[d]
        cumulative_data.append({'x': d, 'y': cum_sum})
        
    topic_progress = []
    dsa_done = len(solved_items)
    
    ext_totals = getattr(user, 'external_totals', {})
    platforms['LeetCode'] = max(platforms['LeetCode'], ext_totals.get('LeetCode', 0))
    platforms['GFG'] = max(platforms['GFG'], ext_totals.get('GFG', 0))
    
    lc_easy = ext_totals.get('LeetCode_Easy', 0)
    lc_medium = ext_totals.get('LeetCode_Medium', 0)
    lc_hard = ext_totals.get('LeetCode_Hard', 0)
    
    lc_contests = ext_totals.get('LeetCode_Contests', 0)
    lc_rating = ext_totals.get('LeetCode_Rating', 0)
    lc_rank = ext_totals.get('LeetCode_GlobalRank', 0)
    
    gh_issues = ext_totals.get('GitHub_Issues', 0)
    gh_prs = ext_totals.get('GitHub_PRs', 0)
    gh_merged = ext_totals.get('GitHub_Merged_PRs', 0)
    gh_commits = ext_totals.get('GitHub_Commits', 0)
    
    global_total_solved = sum(platforms.values())
    total_questions = all_questions.count()
    
    for topic in topics:
        t_id = str(topic.id)
        t_q_ids = topic_q_count.get(t_id, [])
        t_done = sum(1 for q_id in t_q_ids if q_id in solved_items)
        
        percent = (t_done / len(t_q_ids) * 100) if len(t_q_ids) > 0 else 0
        topic_progress.append({
            'name': topic.name,
            'done': t_done,
            'total': len(t_q_ids),
            'percent': round(percent, 1)
        })
        
    topic_progress.sort(key=lambda x: x['done'], reverse=True)
        
    overall_percent = round((dsa_done / total_questions * 100) if total_questions > 0 else 0, 1)
    
    rating_history = list(getattr(user, 'rating_history', []) or [])
    # Parse stored badges from dedicated fields
    lc_badges = []
    hr_badges = []
    try:
        lc_badges = json.loads(getattr(user, 'lc_badges_json', '[]') or '[]')
    except: pass
    try:
        hr_badges = json.loads(getattr(user, 'hr_badges_json', '[]') or '[]')
    except: pass
    return render_template('profile.html',
                           user=user,
                           topic_progress=topic_progress,
                           dsa_done=dsa_done,
                           global_total_solved=global_total_solved,
                           total_questions=total_questions,
                           overall_percent=overall_percent,
                           platforms=platforms,
                           lc_easy=lc_easy,
                           lc_medium=lc_medium,
                           lc_hard=lc_hard,
                           lc_contests=lc_contests,
                           lc_rating=lc_rating,
                           lc_rank=lc_rank,
                           gh_issues=gh_issues,
                           gh_prs=gh_prs,
                           gh_merged=gh_merged,
                           gh_commits=gh_commits,
                           daily_counts=daily_counts,
                           cumulative_data=cumulative_data,
                           total_active_days=total_active_days,
                           rating_history=rating_history,
                           lc_badges=lc_badges,
                           hr_badges=hr_badges)

if __name__ == '__main__':
    app.run(debug=True)
