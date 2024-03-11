from urllib.parse import urljoin
from langchain.schema import messages_to_dict
from langchain_core.messages import BaseMessage
from .base_api import BaseRetrievalServiceAPI, BaseLLMAPI

from langchain_openai import OpenAI, OpenAIEmbeddings


class OpenAIEmbeddingsAPI(BaseRetrievalServiceAPI):
    def __init__(self, solid_utils, api_key: str):
        super().__init__(solid_utils)
        self.api_key = api_key

    def get_embedding_models(self) -> list[str]:
        res = self.session.get("https://api.openai.com/v1/models", headers={ "Authorization": f"Bearer {self.api_key}" })
        return [model["id"] for model in res.json() if "embedding" in model["id"]]

    def get_embeddings(self, selected_model: str) -> None:
        openai = OpenAIEmbeddings(openai_api_key=self.api_key, model=selected_model)
        return super().get_embeddings()
    
    def __str__(self):
        return f"Embeddings provider: OpenAI"


class OpenAILLMAPI(BaseLLMAPI):
    def __init__(self, solid_utils, api_key: str):
        super().__init__(solid_utils)
        self.api_key = api_key

    def get_llm_models(self) -> list[str]:
        res = self.session.get("https://api.openai.com/v1/models", headers={ "Authorization": f"Bearer {self.api_key}" })
        return [model["id"] for model in res.json() if "gpt" in model["id"]]

    def chat_completion(self, selected_llm: str, messages: list[BaseMessage]) -> str:
        openai = OpenAI(openai_api_key=self.api_key, model=selected_llm)
        return ""
    
    def __str__(self):
        return f"LLM provider: OpenAI"
