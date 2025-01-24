from abc import abstractmethod, ABC
from functools import wraps
from inspect import isgeneratorfunction, signature
from typing import Any, Callable, Generator


class YieldDecorator(ABC):

    def __call__(self, func: Callable):

        @wraps(func)
        def wrapper(*args, **kwargs):

            if not isgeneratorfunction(func):
                self.before_call(func)
                result = func(*args, **kwargs)
                return self.after_call(result)

            self.before_call(*args, **kwargs)
            generator: Generator = func(*args, **kwargs)
            result = None
            try:
                yield_result: Any = next(generator)
                while True:
                    yield_result = self.validate_yield(yield_result)
                    result = self.after_yield(yield_result)
                    yield_result = generator.send(result)
            except StopIteration as e:
                result = e.value
            return self.after_call(result)

        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = signature(func).return_annotation
        return wrapper

    def before_call(self, *args, **kwargs): ...

    def validate_yield(self, yield_result: Any) -> Any:
        return yield_result

    @abstractmethod
    def after_yield(self, yield_result: Any) -> Any:
        pass

    def after_call(self, result: Any) -> Any:
        return result
