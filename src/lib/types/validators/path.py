from pathlib import Path
from pydantic import ValidationInfo, ValidatorFunctionWrapHandler


def directory_validator(
    value: str, handler: ValidatorFunctionWrapHandler, _info: ValidationInfo
) -> Path:
    # check if path exists and is a directory
    path = Path(value)
    if not path.exists():
        raise ValueError(f"Path {path} does not exist")
    if not path.is_dir():
        raise ValueError(f"Path {path} is not a directory")
    return path
