from abc import abstractmethod, ABC
from functools import wraps
from inspect import isgeneratorfunction, signature
from typing import Any, Callable, Generator


class YieldDecorator(ABC):

    def __call__(self, func: Callable):
        
        # if func is burr action
        # if func is hamilton node
        # if func is partial

        @wraps(func)
        def wrapper(*args, **kwargs):

            # if function is not generator,
            # either it's cached or it's just impl wrong
            # return the result directly
            if not isgeneratorfunction(func):
                self.before_call(func)
                result = func(*args, **kwargs)
                return self.after_call(result)
            
            self.before_call(*args, **kwargs)
            generator:Generator = func(*args, **kwargs)
            result = None
            try:
                yield_result: Any = next(generator)
                while True:
                    yield_result = self.validate_yield(yield_result)
                    result = self.after_yield(yield_result)
                    yield_result = generator.send(result)
                # ValueError should not be hit because a StopIteration should be raised, unless
                # there are multiple yields in the generator.
                # raise ValueError("Generator cannot have multiple yields.")
                # raise StopIteration(result)
            except StopIteration as e:
                result = e.value
            return self.after_call(result)

        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = signature(func).return_annotation
        return wrapper

    def before_call(self, *args, **kwargs):
        ...

    def validate_yield(self, yield_result: Any) -> Any:
        return yield_result

    @abstractmethod
    def after_yield(self, yield_result: Any) -> Any:
        pass

    def after_call(self, result: Any) -> Any:
        return result
