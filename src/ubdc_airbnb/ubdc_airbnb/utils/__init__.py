# util functions that do not require db access


def get_random_string(length: int = 10) -> str:
    """Generate a random string of fixed length."""
    import random
    import string

    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for i in range(length))
