from flask.ext.wtf import Form
from wtforms import StringField, PasswordField,DecimalField
from wtforms.validators import DataRequired

class LoginForm(Form):
	usr = StringField('user name', validators=[DataRequired()])
	pas = PasswordField('password', validators=[DataRequired()])

class WishlistSearchForm(Form):
	search = StringField('search term', validators=[DataRequired()])

class InventoryAddForm(Form):
	item = StringField('inventory item', validators=[DataRequired()])
	price = DecimalField('price', validators=[DataRequired()])
