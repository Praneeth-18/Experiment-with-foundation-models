from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
from PIL import Image
import urllib.request
import json
import os
import ssl
from pylint import epylint as lint
import tempfile
import subprocess
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a random secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///code_review_system.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    points = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Submission model
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), nullable=False)
    feedback = db.Column(db.Text)
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))

# PeerReview model
class PeerReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    review = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submission = db.relationship('Submission', backref=db.backref('peer_reviews', lazy=True))
    reviewer = db.relationship('User', backref=db.backref('reviews_given', lazy=True))

# ForumPost model
class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('forum_posts', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('dashboard.html', submissions=submissions)

@app.route('/submit_code', methods=['GET', 'POST'])
@login_required
def submit_code():
    if request.method == 'POST':
        code = request.form['code']
        language = request.form['language']
        submission = Submission(user_id=current_user.id, code=code, language=language)
        db.session.add(submission)
        db.session.commit()
        return redirect(url_for('code_analysis', submission_id=submission.id))
    return render_template('submit_code.html')

@app.route('/code_analysis/<int:submission_id>')
@login_required
def code_analysis(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    feedback, score = analyze_code(submission.code, submission.language)
    submission.feedback = feedback
    submission.score = score
    db.session.commit()
    return render_template('code_analysis.html', submission=submission)

def analyze_code(code, language):
    if language.lower() == 'python':
        return analyze_python_code(code)
    elif language.lower() == 'javascript':
        return analyze_javascript_code(code)
    else:
        return f"Code analysis for {language} is not implemented yet.", 0.0

def analyze_python_code(code):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        (pylint_stdout, pylint_stderr) = lint.py_run(temp_file_path, return_std=True)
        feedback = pylint_stdout.getvalue()
        
        # Extract the score from the feedback
        score_line = [line for line in feedback.split('\n') if line.startswith('Your code has been rated at')]
        if score_line:
            score = float(score_line[0].split()[6].split('/')[0])
        else:
            score = 0.0

        return feedback, score
    finally:
        os.unlink(temp_file_path)

def analyze_javascript_code(code):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        result = subprocess.run(['npx', 'eslint', '-f', 'json', temp_file_path], capture_output=True, text=True)
        eslint_output = json.loads(result.stdout)

        if eslint_output:
            total_problems = sum(file['errorCount'] + file['warningCount'] for file in eslint_output)
            feedback = f"Total issues found: {total_problems}\n\n"
            for file in eslint_output:
                for message in file['messages']:
                    feedback += f"Line {message['line']}: {message['message']} ({message['ruleId']})\n"
            
            # Calculate a score based on the number of issues (you can adjust this calculation)
            score = max(0, 10 - total_problems)
        else:
            feedback = "No issues found."
            score = 10.0

        return feedback, score
    except subprocess.CalledProcessError as e:
        return f"Error running ESLint: {e}", 0.0
    finally:
        os.unlink(temp_file_path)

@app.route('/peer_review/<int:submission_id>', methods=['GET', 'POST'])
@login_required
def peer_review(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.user_id == current_user.id:
        flash('You cannot review your own submission.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        review = request.form['review']
        new_review = PeerReview(submission_id=submission_id, reviewer_id=current_user.id, review=review)
        db.session.add(new_review)
        current_user.points += 5  # Award points for submitting a review
        db.session.commit()
        flash('Your review has been submitted. You earned 5 points!')
        return redirect(url_for('dashboard'))
    
    return render_template('peer_review.html', submission=submission)

@app.route('/submissions_for_review')
@login_required
def submissions_for_review():
    submissions = Submission.query.filter(Submission.user_id != current_user.id).order_by(Submission.created_at.desc()).limit(10).all()
    return render_template('submissions_for_review.html', submissions=submissions)

@app.route('/my_submissions')
@login_required
def my_submissions():
    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('my_submissions.html', submissions=submissions)

@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.order_by(User.points.desc()).limit(10).all()
    return render_template('leaderboard.html', users=users)

@app.route('/forum')
@login_required
def forum():
    posts = ForumPost.query.order_by(ForumPost.created_at.desc()).all()
    return render_template('forum.html', posts=posts)

@app.route('/forum/new', methods=['GET', 'POST'])
@login_required
def new_forum_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        post = ForumPost(title=title, content=content, user_id=current_user.id)
        db.session.add(post)
        current_user.points += 2  # Award points for creating a forum post
        db.session.commit()
        flash('Your post has been created! You earned 2 points.')
        return redirect(url_for('forum'))
    return render_template('new_forum_post.html')

@app.route('/forum/<int:post_id>')
@login_required
def view_forum_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    return render_template('view_forum_post.html', post=post)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
