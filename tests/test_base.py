from h_submitor.base import YieldDecorator

class YieldDecoratorTester(YieldDecorator):

    def __init__(self):
        self.before_call_called = False
        self.validate_yield_called = False
        self.after_yield_called = False
        self.after_call_called = False

    def before_call(self, func):
        self.before_call_called = True

    def validate_yield(self, config):
        self.validate_yield_called = True
        return config
    
    def after_yield(self, config):
        self.after_yield_called = True
        return config
    
    def after_call(self, result):
        self.after_call_called = True
        return result

class TestYieldDecorator:

    def test_generator(self):
        
        yield_decorator_tester = YieldDecoratorTester()

        @yield_decorator_tester
        def foo():
            assert yield_decorator_tester.before_call_called
            result = yield {"a": 1}
            assert result == {"a": 1}
            assert yield_decorator_tester.validate_yield_called
            result = yield {"a": 2}
            assert result == {"a": 2}
            return {"a": 3}

        foo()
        assert yield_decorator_tester.after_call_called

    