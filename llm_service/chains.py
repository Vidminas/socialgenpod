from typing import Any, Dict

from langchain.chains import ConversationalRetrievalChain

from .llms import get_llm
from .vectorstores import get_vectorstore


def make_conversation_chain(
    config: Dict[str, Any],
    *,
    selected_llm_index: int = 0,
) -> ConversationalRetrievalChain:
    db = get_vectorstore(config)
    retriever = db.as_retriever(**config["retriever"])
    llm = get_llm(config, selected_llm_index=selected_llm_index)
    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
    )
