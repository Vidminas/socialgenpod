from abc import ABC
from langchain_core.messages import BaseMessage
from requests import Session

session = Session()


class BaseEmbeddingsAPI(ABC):
    """
    Generic abstract class that contains endpoints and route handling for embeddings providers
    """

    def __init__(self):
        self.session = session

    def get_embeddings(self) -> None:
        pass


class BaseLLMAPI(ABC):
    """
    Generic abstract class that contains endpoints and route handling for LLM providers
    """

    def __init__(self):
        self.session = session

    def get_llm_models(self) -> list[str]:
        pass

    def chat_completion(self, selected_llm: str, messages: list[BaseMessage]) -> str:
        pass
