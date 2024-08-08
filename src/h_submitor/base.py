from functools import wraps
from typing import Callable, Any
from inspect import isgeneratorfunction, signature
from abc import ABC, abstractmethod, ABCMeta
from hamilton.function_modifiers import tag

import subprocess

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

class cmdline(YieldDecorator):
    """Decorator to run the result of a function as a command line command.
    """

    def modify_func(self, func: Callable)->Callable:
        func = tag(cmdline='true')(func)
        return func

    def validate_config(self, config: dict)->dict:

        default_config = {
            'block': True,
            'kwargs': {
                'capture_output': True,
                'shell': False,
            }
        }

        config |= default_config
        
        cmd = config.get('cmd')
        assert isinstance(cmd, (list, str)), ValueError(f"cmd must be a list of string or a string, got {type(cmd)}")

        return config

    def do(self, config: dict) -> subprocess.CompletedProcess:

        cmd = config.get('cmd')
        kwargs = config.get('kwargs')

        result = subprocess.run(cmd, **kwargs)

        return result
        
