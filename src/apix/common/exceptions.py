class ApixError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ContractError(ApixError):
    def __init__(self, message: str) -> None:
        super().__init__("CONTRACT", message)


class QualityError(ApixError):
    def __init__(self, message: str) -> None:
        super().__init__("QUALITY", message)


class SampleError(ApixError):
    def __init__(self, message: str) -> None:
        super().__init__("SAMPLE", message)


class ConfigError(ApixError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFIG", message)
