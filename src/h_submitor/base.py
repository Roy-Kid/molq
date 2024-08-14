from abc import ABC, ABCMeta, abstractmethod
from functools import wraps
from inspect import isgeneratorfunction, signature
from typing import Any, Callable

from hamilton.function_modifiers import tag


class YieldDecoratorMeta(ABCMeta):

    def __call__(cls, *args, **kwargs):
        
        if len(args) == 1 and isgeneratorfunction(args[0]):
            ins = cls.__new__(cls)
            return ins.__call__(args[0])
        else:
            return super().__call__(*args, **kwargs)

class YieldDecorator(metaclass=YieldDecoratorMeta):

    def __call__(self, func: Callable):

        if not isgeneratorfunction(func):
            raise TypeError(f"Function {func.__name__} must be a generator function")
        
        func = self.modify_func(func)

        @wraps(func)
        def wrapper(*args, **kwargs):

            generator = func(*args, **kwargs)
            config: dict = next(generator)
            config = self.validate_config(config)

            # do something
            result = self.do(config)

            try:
                generator.send(result)
                # ValueError should not be hit because a StopIteration should be raised, unless
                # there are multiple yields in the generator.
                raise ValueError("Generator cannot have multiple yields.")
            except StopIteration as e:
                result = e.value

            return result

        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = signature(func).return_annotation
        return wrapper
    
    @abstractmethod
    def modify_func(self, func: Callable)->Callable:
        pass

    @abstractmethod
    def do(self, config: dict):
        pass

    @abstractmethod
    def validate_config(self, config: dict)->dict:
        pass

