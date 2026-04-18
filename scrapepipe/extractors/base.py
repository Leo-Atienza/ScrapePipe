from abc import ABC, abstractmethod

from scrapepipe.models import SocialPost


class Extractor(ABC):
    @abstractmethod
    def fetch(self, url: str) -> SocialPost:
        ...
