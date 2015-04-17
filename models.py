from flask.ext.login import UserMixin

class User(UserMixin):
    '''Simple User class'''

    def __init__(self, id):
        self.id = id

    @classmethod
    def get(self_class, id):
        '''Return user instance of id, return None if not exist'''
        try:
            return self_class(id)
        except UserNotFoundError:
            return None

"""
Exceptions
"""

class UserNotFoundError(Exception):
    pass
