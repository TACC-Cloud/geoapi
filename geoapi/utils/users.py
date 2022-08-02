class AnonymousUser:
    username = "Guest"


def is_anonymous(user):
    return isinstance(user, AnonymousUser)