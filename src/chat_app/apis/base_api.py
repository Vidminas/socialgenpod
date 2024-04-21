from abc import ABC
from typing import Optional

from langchain.schema import BaseMessage, Document
from requests import Session

from chat_app.solid_pod_utils import SolidPodUtils


class BaseRetrievalServiceAPI(ABC):
    """
    Generic abstract class that contains endpoints and route handling for retrieval service providers
    """

    def __init__(self, solid_utils: SolidPodUtils):
        self.session = Session()
        self.solid_utils = solid_utils

    def get_embedding_models(self) -> list[str]:
        pass

    def add_documents(self, selected_model: str, docs_location: str):
        pass

    def find_relevant_context(
        self, selected_model: str, docs_location: str, query: str
    ) -> list[Document]:
        pass


class BaseLLMAPI(ABC):
    """
    Generic abstract class that contains endpoints and route handling for LLM providers
    """

    def __init__(self, solid_utils: SolidPodUtils):
        self.session = Session()
        self.solid_utils = solid_utils

    def get_llm_models(self) -> list[str]:
        pass

    def condense_prompt_with_chat_history(self, selected_llm: str, messages: list[BaseMessage]) -> str:
        pass

    def chat_completion(
        self, selected_llm: str, prompt: str, relevant_documents: Optional[list[Document]]
    ) -> str:
        pass
