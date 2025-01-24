from nest.core import Injectable

import os
import logging

from src.lib.base_config import BASE_CONFIG


logger = logging.getLogger(__name__)


@Injectable
class ZerePyService:
    cfg = BASE_CONFIG

    def version(self) -> str:
        return f"ZerePy version: {self.cfg.version}"
