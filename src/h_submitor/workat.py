from .base import YieldDecorator
from pathlib import Path

class workat(YieldDecorator):

    def validate_yield(self, path: str | Path):
        return Path(path)
    
    def after_yield(self, yield_result: Path):
        yield_result.mkdir(parents=True, exist_ok=True)
        return yield_result

    def after_call(self, result):
        return result
