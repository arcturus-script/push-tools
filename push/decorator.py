def catchException(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            name = args[0].__class__.__name__

            print(f"[{name}] Message sent failed, because: {e}")

    return wrapper
