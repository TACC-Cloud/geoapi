class AnonymousUser:
    """
    Represents an anonymous user.

    Attributes:
        username (str): A unique username for the anonymous user, prefixed by 'Guest_'.
                       If no `guest_unique_id` is provided, username defaults to 'Guest_Unknown'.

    Args:
        guest_unique_id (Optional[str]): A unique identifier for the guest user.
    """

    def __init__(self, guest_unique_id=None):
        guest_uid = guest_unique_id if guest_unique_id else "Unknown"
        self.username = f"Guest_{guest_uid}"


def is_anonymous(user):
    return isinstance(user, AnonymousUser)
