def catch_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            name = args[0].__class__.__name__
            err_type = type(e).__name__

            print(f"[{name}] An error occurred, because > {err_type}: {e}")

    return wrapper


class AccessFailed(Exception):
    pass
