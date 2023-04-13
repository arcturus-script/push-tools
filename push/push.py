from abc import ABC, abstractmethod


class Push(ABC):
    def __init__(self, key: str | dict) -> None:
        super().__init__()

        self.key = key

    @abstractmethod
    def send(self, msg: str, **kwargs) -> None:
        pass

    def success(self):
        name = self.__class__.__name__
        print(f"[{name}] Message sent successfully.")
