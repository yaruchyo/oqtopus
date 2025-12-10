from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data.get("_id"))
        self.username = user_data.get("username")
        self.email = user_data.get("email")
        self.password_hash = user_data.get("password_hash")
