from abc import ABC, abstractmethod


class push(ABC):
    def __init__(self, key):
        super().__init__()
        self.key = key

    @abstractmethod
    def send(self, msg, **kwargs):
        pass

    def success(self, *args):
        name = self.__class__.__name__

        if args:
            print(f"[{name}]", *args)
        else:
            print(f"[{name}] Operate successfully.")
