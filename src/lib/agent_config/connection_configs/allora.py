from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from src.lib.types import BlockchainNetwork


class AlloraSettings(BaseSettings):
    api_key: str = Field(validation_alias="ALLORA_API_KEY")


class AlloraConfig(BaseModel):
    chain: BlockchainNetwork
    allora_settings: AlloraSettings

    def __init__(self, **data) -> None:
        # if the connection is not configured, return none
        try:
            data["allora_settings"] = AlloraSettings()
            super().__init__(**data)

        except Exception as e:
            return
