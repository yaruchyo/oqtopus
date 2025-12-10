from bson.objectid import ObjectId
from werkzeug.security import check_password_hash, generate_password_hash

from agent_package.domain_layer.user_domain import User


def hash_password(password):
    return generate_password_hash(password)


def check_password(pwhash, password):
    return check_password_hash(pwhash, password)


def load_user_from_db(storage_type, user_id, db_connection):
    query_id = user_id
    if storage_type == "mongodb":
        query_id = ObjectId(user_id)
    user_data = db_connection.find_document("users", {"_id": query_id})
    if user_data:
        return User(user_data)
    return None
