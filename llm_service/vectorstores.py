from typing import Any, Dict, List

from chromadb.config import Settings
from langchain.docstore.document import Document
from langchain.vectorstores.chroma import Chroma

from .embeddings import get_embeddings


def get_vectorstore(config: Dict[str, Any]) -> Chroma:
    embeddings = get_embeddings(config)
    config = config["chroma"]
    return Chroma(
        embedding_function=embeddings,
        client_settings=Settings(**config),
    )


def get_vectorstore_from_documents(
    config: Dict[str, Any],
    documents: List[Document],
) -> Chroma:
    embeddings = get_embeddings(config)
    config = config["chroma"]
    return Chroma.from_documents(
        documents,
        embeddings,
        client_settings=Settings(**config),
    )
