from urllib.parse import urljoin
from langchain.schema import messages_to_dict
from langchain_core.messages import BaseMessage
from .base_api import BaseEmbeddingsAPI, BaseLLMAPI


class DemoEmbeddingsAPI(BaseEmbeddingsAPI):
    def __init__(self, embeddings_provider_url: str):
        super().__init__()
        self.embeddings_provider_url = (
            embeddings_provider_url
            if embeddings_provider_url.endswith("/")
            else f"{embeddings_provider_url}/"
        )

    def get_embeddings(self) -> None:
        return super().get_embeddings()
    
    def __str__(self):
        return f"Demo embeddings provider: {self.embeddings_provider_url}"


class DemoLLMAPI(BaseLLMAPI):
    def __init__(self, llm_provider_url: str):
        super().__init__()
        self.llm_provider_url = (
            llm_provider_url
            if llm_provider_url.endswith("/")
            else f"{llm_provider_url}/"
        )

    def get_llm_models(self) -> list[str]:
        response = self.session.get(urljoin(self.llm_provider_url, "models/"))
        if not response.is_redirect:
            response.raise_for_status()
        return response.json()

    def chat_completion(self, selected_llm: str, messages: list[BaseMessage]) -> str:
        response = self.session.post(
            urljoin(self.llm_provider_url, "completions/"),
            json={
                "model": selected_llm,
                "messages": messages_to_dict(messages),
            },
        )
        if not response.is_redirect:
            response.raise_for_status()
        return response.text
    
    def __str__(self):
        return f"Demo LLM provider: {self.llm_provider_url}"
