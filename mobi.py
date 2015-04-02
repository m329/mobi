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

app = Flask(__name__)

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
	return render_template('index.html')

@app.route("/chat")
def chat():
	""" show chat page """
	return render_template('chat.html')

"""
SocketIO	
"""

@socketio.on('message', namespace='/thechat')
def send_message(message):
	escaped_message = Markup.escape(message['data']) # escape the message before broadcasting it!
	emit('response',{'data': escaped_message},broadcast=True)

@socketio.on('disconnect request', namespace='/thechat')
def disconnect_request():
	emit('response',{'data': 'You have been disconnected.'})
	disconnect()
	
@socketio.on('connect', namespace='/thechat')
def thechat_connect():
	emit('response', {'data': 'You are now connected.'})

@socketio.on('disconnect', namespace='/thechat')
def thechat_disconnect():
	print('The client has disconnected.')

# if this module is called directly, run the app
if __name__ == "__main__":
	socketio.run(app)
