# -*- coding: utf-8 -*-

"""
Mobi
~~~~~~
"Mobile garage sale" takes the hassle out of buying and selling stuff on-the-go.

"""

from gevent import monkey
monkey.patch_all()

import os, sys
import json, sqlite3
from flask import Flask, render_template, g, request, flash, redirect, url_for, session, Markup
import requests
import config
from flask.ext.socketio import SocketIO, emit, disconnect
from flask.ext.login import LoginManager, login_required, login_user, logout_user, current_user
from forms import LoginForm
from models import User
import hashlib

app = Flask(__name__)

lm = LoginManager()
lm.init_app(app)

"""
DB-related
"""

# Load/override default config
app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'mobi.db'),
	DEBUG=config.DEBUG,
	SECRET_KEY=config.SECRET_KEY
))

socketio = SocketIO(app)

def connect_db():
	""" connect to the specific database """
	rv = sqlite3.connect(app.config['DATABASE'])
	rv.row_factory = sqlite3.Row
	return rv

def get_db():
	"""	open a new database connection if there is none yet for the current application context """
	if not hasattr(g, 'sqlite_db'):
		g.sqlite_db = connect_db()
	return g.sqlite_db

def init_db():
	""" initialize the database """
	with app.app_context():
		db = get_db()
		with app.open_resource('schema.sql', mode='r') as f:
			db.cursor().executescript(f.read())
		db.commit()

@app.teardown_appcontext
def close_db(error):
	""" close the database connection """
	if hasattr(g, 'sqlite_db'):
		g.sqlite_db.close()

"""
View functions
"""

@app.route("/")
def index():
	""" show front page """
	return render_template('index.html',user=g.user)

@app.route("/chat")
@login_required
def chat():
	""" show chat page """
	return render_template('chat.html',user=g.user)

@app.route("/login", methods=["GET", "POST"])
def login():
	db = get_db()
	
	form = LoginForm()
	if form.validate_on_submit():
		# login and validate the user...
		user = User.get(request.form['usr'])

		cur = db.execute('select pas from users where usr=?',[request.form['usr']])
		user.password = cur.fetchone()[0]
		
		if (user and user.password == hashlib.sha224(request.form['usr']+':'+request.form['pas']).hexdigest()):
			login_user(user)
			flash("Logged in successfully.", 'success')
			return redirect(url_for('index'))
		else:
			flash('Username or password incorrect.', 'danger')
	return render_template("login.html", user=g.user, form=form)

def require_login():
	flash("You must login to view this page!", 'danger')
	return redirect(url_for('login'))
    
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out successfully.", 'success')
    return redirect(url_for('index'))

@app.route("/settings")
@login_required
def settings():
    pass

"""
Users and login
"""

@lm.user_loader
def load_user(userid):
    return User.get(userid)
    
lm.unauthorized_handler(require_login)

@app.before_request
def before_request():
    g.user = current_user

"""
SocketIO	
"""

@socketio.on('message', namespace='/thechat')
def send_message(message):
	if current_user.is_authenticated():
		escaped_message = Markup.escape(message['data']) # escape the message before broadcasting it!
		emit('response',{'data': escaped_message, 'user': current_user.id},broadcast=True)
	else:
		disconnect()

@socketio.on('disconnect request', namespace='/thechat')
def disconnect_request():
	emit('response',{'data': 'You have been disconnected.', 'user': 'system'})
	disconnect()

@socketio.on('connect', namespace='/thechat')
def thechat_connect():
	if current_user.is_authenticated():
		emit('response', {'data': 'You are now connected.', 'user': 'system'})
	else:
		disconnect()

@socketio.on('disconnect', namespace='/thechat')
def thechat_disconnect():
	print('The client has disconnected.')

# if this module is called directly, run the app
if __name__ == "__main__":
	socketio.run(app)
