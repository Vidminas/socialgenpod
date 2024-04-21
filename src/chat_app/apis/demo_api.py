from urllib.parse import urljoin
from typing import Optional

import requests
from langchain.schema import BaseMessage, Document, messages_to_dict

from .base_api import BaseRetrievalServiceAPI, BaseLLMAPI
from chat_app.solid_pod_utils import SolidPodUtils


class DemoEmbeddingsAPI(BaseRetrievalServiceAPI):
    def __init__(self, solid_utils: SolidPodUtils, embeddings_provider_url: str):
        super().__init__(solid_utils)
        self.embeddings_provider_url = (
            embeddings_provider_url
            if embeddings_provider_url.endswith("/")
            else f"{embeddings_provider_url}/"
        )
        try:
            res = self.session.get(self.embeddings_provider_url)
            if not res.ok:
                raise RuntimeError(
                    "Error communicating with embeddings provider: " + res.text
                )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                "Error communicating with embeddings provider: " + str(e)
            )

    def get_embedding_models(self) -> list[str]:
        response = self.session.get(
            urljoin(self.embeddings_provider_url, "embeddings/models/")
        )
        if not response.is_redirect:
            response.raise_for_status()
        return response.json()
    
    def add_documents(self, selected_model: str, docs_location: str):
        res = self.session.post(
            urljoin(self.embeddings_provider_url, "embeddings/add/"),
            json={
                "model": selected_model,
                "docs_location": docs_location,
            },
            headers={
                "webid": self.solid_utils.solid_auth.get_web_id(),
            }
        )
        if not res.ok:
            raise RuntimeError(res.text)

    def find_relevant_context(
        self, selected_model: str, docs_location: str, query: str
    ) -> list[Document]:
        url = urljoin(self.embeddings_provider_url, "embeddings/query/")
        res = self.session.post(
            url,
            json={
                "model": selected_model,
                "docs_location": docs_location,
                "query": query,
            },
            headers={
                **self.solid_utils.solid_auth.get_auth_headers(url, "POST"),
                "webid": self.solid_utils.solid_auth.get_web_id(),
            }
        )
        if not res.ok:
            raise RuntimeError(res.text)
        return [
            Document(page_content=obj["page_content"], metadata=obj["metadata"])
            for obj in res.json()
        ]

    def __str__(self):
        return f"Demo retrieval service provider: {self.embeddings_provider_url}"


class DemoLLMAPI(BaseLLMAPI):
    def __init__(self, solid_utils: SolidPodUtils, llm_provider_url: str):
        super().__init__(solid_utils)
        self.llm_provider_url = (
            llm_provider_url
            if llm_provider_url.endswith("/")
            else f"{llm_provider_url}/"
        )
        try:
            res = self.session.get(self.llm_provider_url)
            if not res.ok:
                raise RuntimeError("Error communicating with LLM provider: " + res.text)
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError("Error communicating with LLM provider: " + str(e))

    def get_llm_models(self) -> list[str]:
        response = self.session.get(urljoin(self.llm_provider_url, "models/"))
        if not response.is_redirect:
            response.raise_for_status()
        return response.json()
    
    def condense_prompt_with_chat_history(self, selected_llm: str, messages: list[BaseMessage]) -> str:
        response = self.session.post(
            urljoin(self.llm_provider_url, "rephrase/"),
            json={
                "model": selected_llm,
                "messages": messages_to_dict(messages),
            }
        )
        if not response.is_redirect:
            response.raise_for_status()
        return response.text

    def chat_completion(
        self, selected_llm: str, prompt: str, relevant_documents: Optional[list[Document]]
    ) -> str:
        response = self.session.post(
            urljoin(self.llm_provider_url, "completions/"),
            json={
                "model": selected_llm,
                "prompt": prompt,
                "context": [doc.to_json() for doc in relevant_documents] if relevant_documents else [],
            },
        )
        if not response.is_redirect:
            response.raise_for_status()
        return response.text

    def __str__(self):
        return f"Demo LLM provider: {self.llm_provider_url}"
