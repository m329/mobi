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
from flask.ext.socketio import SocketIO, emit, disconnect, join_room, leave_room, send
from flask.ext.login import LoginManager, login_required, login_user, logout_user, current_user
from forms import LoginForm, WishlistSearchForm, InventoryAddForm
from models import User
import hashlib
import geohash

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
@app.route("/<asklocation>")
def index(asklocation=''):
	""" show front page """
	return render_template('index.html',user=g.user,asklocation=asklocation)

@app.route("/chat")
@login_required
def chat():
	""" show chat page """
	return render_template('chat.html',user=g.user)

@app.route("/private/<u1>/<u2>/<item>")
@login_required
def chat_pairwise(u1,u2,item):
	""" show pairwise chat page """
	db = get_db()
	cur = db.execute('select itm_name from items where itm_id=?',[item])
	result = cur.fetchone()
	
	item_name = None
	
	if len(result) > 0:
		item_name = result[0]
	else:
		return redirect(url_for('chat'))
		
	if g.user.id not in [u1,u2]:
		return redirect(url_for('chat'))
		
	pair = [u1,u2]
	pair.remove(g.user.id)
	otheruser=pair[0]
	
	socketio.emit('response', {'data': g.user.id+' wants to chat with you about '+item_name+'!', 'url':'/private/'+u1+'/'+u2+'/'+item}, room=otheruser, namespace='/personal')
	
	return render_template('chat_pairwise.html',room='|'.join(sorted([u1,u2])),user=g.user,otheruser=otheruser,about_item=item_name)

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
			return redirect(url_for('index',asklocation='askgeo'))
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
Geolocation
"""
@app.route("/geolocation/update",methods=["POST"])
@login_required
def update_geolocation():

	lat = float(request.form['latitude'])
	lon = float(request.form['longitude'])

	db = get_db()
	
	print "lat: "+str(lat)
	print "lon: "+str(lon)
	
	gh = geohash.encode(lat,lon)[:5]
	
	db.execute("update users set lat=?, lon=?, geohash=? where usr=?",[lat,lon,gh,g.user.id])
	db.commit()
	return "[]"

def get_user_geohash(userid=None):
	if userid is None:
		userid = g.user.id
	db = get_db()
	cur = db.execute("select geohash from users where usr=?",[g.user.id])
	gh = cur.fetchone()[0]
	return gh

"""
Inventory
"""

@app.route("/inventory",methods=['GET','POST'])
@login_required
def inventory():
	
	db = get_db()
	
	form=InventoryAddForm()
	if form.validate_on_submit():
		item_name = Markup.escape(request.form['item']) # escape the search term before broadcasting it!
		price = Markup.escape(request.form['price'])
		
		db.execute("insert into items (itm_name, usr, prc) values(?, ?, ?);",[item_name,g.user.id, price])
		db.commit()

	cur = db.execute("select itm_id, itm_name, prc from items where usr=?",[g.user.id])
	items = cur.fetchall()
	return render_template("inventory.html", user=g.user, items=items, form=form)

@app.route("/inventory/delete/<id>", methods=["GET"])
@login_required
def inventory_delete(id):
	
	id = Markup.escape(id) # escape
	
	db = get_db()
	
	db.execute("delete from items where usr=? and itm_id=?",[g.user.id, id])
	db.commit()
	
	return redirect(url_for('inventory'))

@app.route("/wishlist/nearby")
@login_required
def wishlist_nearby():
	
	gh = get_user_geohash()
	
	neighbors = geohash.neighbors(gh)
	neighbors.append(gh)
	neighborhood = "('"+"','".join(neighbors)+"')"
		
	db = get_db()
	cur = db.execute("select I.itm_name, I.prc, U.usr as owner, I.itm_id from items as I join users as U on I.usr=U.usr join (select * from wishlists as WI join users as US on WI.usr = US.usr) as W where U.usr!=? and W.usr=? and I.itm_name like '%'||W.wishstr||'%' and U.geohash in "+neighborhood+";",[g.user.id, g.user.id])
	items = cur.fetchall()
	return render_template("wishlist_nearby.html", user=g.user, items=items)

@app.route("/wishlist/search/delete/<term>", methods=["GET"])
@login_required
def wishlist_search_delete(term):
	
	term = Markup.escape(term) # escape
	
	db = get_db()
	
	db.execute("delete from wishlists where usr=? and wishstr=?",[g.user.id, term])
	db.commit()
	
	return redirect(url_for('wishlist_search'))
	
	
@app.route("/wishlist/search", methods=["GET", "POST"])
@login_required
def wishlist_search():

	db = get_db()
	
	form=WishlistSearchForm()
	if form.validate_on_submit():
		term = Markup.escape(request.form['search']) # escape the search term before broadcasting it!
		db.execute("insert into wishlists (usr,wishstr) values(?,?)",[g.user.id, term])
		db.commit()

	cur = db.execute("select wishstr from wishlists where usr=?",[g.user.id])
	items = cur.fetchall()
	items = [i[0] for i in items]
	return render_template("wishlist_search.html", user=g.user, items=items, form=form)

	

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

# Private rooms
@socketio.on('connect', namespace='/private')
def private_connect():
	if current_user.is_authenticated():
		emit('response', {'data': 'You are now connected.', 'user': 'system'})
	else:
		disconnect()

@socketio.on('disconnect', namespace='/private')
def private_disconnect():
	print('The client has disconnected.')

@socketio.on('join', namespace='/private')
def private_on_join(data):
    username = current_user.id
    room = data['room']
    if username in room.split('|'):
		join_room(room)
		send(username + ' has entered the room.', room=room)

@socketio.on('leave', namespace='/private')
def private_on_leave(data):
    username = current_user.id
    room = data['room']
    if username in room.split('|'):
		leave_room(room)
		send(username + ' has left the room.', room=room)

@socketio.on('message', namespace='/private')
def private_send_message(message):
	
	username = current_user.id
	room = message['room']

	if current_user.is_authenticated() and username in room.split('|'):
			escaped_message = Markup.escape(message['data']) # escape the message before broadcasting it!
			emit('response',{'data': escaped_message, 'user': current_user.id},room=message['room'], broadcast=True)
		
	else:
		disconnect()

"""
Personal
"""

@socketio.on('connect', namespace='/personal')
def personal_connect():	
	if current_user.is_authenticated():
		#emit('response', {'data': 'You are now connected.', 'user': 'system'})
		join_room(current_user.id)
		
	else:
		disconnect()

@socketio.on('disconnect', namespace='/personal')
def personal_disconnect():
	print('The client has disconnected.')


# if this module is called directly, run the app
if __name__ == "__main__":
	socketio.run(app)
