from typing import Optional

import requests
from fastapi import FastAPI, Depends, Header, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from langchain.schema import messages_from_dict, Document
from langchain_core.load import load

from .config import get_config
from .add import add
from .embeddings import get_retriever_for_webid
from .llms import get_llm, llm_rephrase_question_with_history, llm_respond
from .solid_utils import check_uri_access

############
### Main ###
############
app = FastAPI()

origins = [
    # "http://localhost:8080",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = get_config()


@app.get("/")
def read_root():
    return {"Hello": "World"}


#########################
### Retrieval service ###
#########################
@app.get("/embeddings/models/")
def get_embedding_models() -> list[str]:
    return [config["embeddings"]["model"]]


class EmbeddingsAddData(BaseModel):
    model: str
    docs_location: str


@app.post("/embeddings/add/")
def add_documents(data: EmbeddingsAddData, webid: Optional[str] = Header(None)):
    if webid is None:
        raise HTTPException(status_code=400, detail="No webid supplied!")

    try:
        if not check_uri_access(data.docs_location):
            raise HTTPException(
                status_code=400,
                detail="Retrieval service cannot access " + data.docs_location,
            )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=400,
            detail="Retrieval service cannot access "
            + data.docs_location
            + "\n"
            + str(e),
        )

    add(config, data.docs_location, webid)


class EmbeddingsRequestData(BaseModel):
    model: str
    docs_location: str
    query: str


@app.post("/embeddings/query/")
def retrieve_relevant_documents(
    data: EmbeddingsRequestData,
    webid: Optional[str] = Header(None),
):
    if webid is None:
        raise HTTPException(status_code=400, detail="No webid supplied!")

    retriever = get_retriever_for_webid(config, webid)
    docs = retriever.invoke(data.query)
    return docs


###################
### LLM service ###
###################
@app.get("/models/")
def get_llm_models() -> list[str]:
    return list(map(lambda llm: llm.get("model"), config["llms"]))


class ChatRephraseRequestData(BaseModel):
    model: str
    messages: list[dict]


@app.post("/rephrase/")
def rephrase_prompt_with_chat_history(data: ChatRephraseRequestData) -> str:
    try:
        selected_model_idx = [llm["model"] for llm in config["llms"]].index(data.model)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model selection")

    messages = messages_from_dict(data.messages)
    llm = get_llm(config, selected_llm_index=selected_model_idx)
    response = llm_rephrase_question_with_history(
        llm, prompt=messages[-1].content, chat_history=messages[:-1]
    )
    return response


class ChatCompletionRequestData(BaseModel):
    model: str
    prompt: str
    context: Optional[list[dict]]


@app.post("/completions/")
def chat_completion(data: ChatCompletionRequestData) -> str:
    try:
        selected_model_idx = [llm["model"] for llm in config["llms"]].index(data.model)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model selection")
    
    llm = get_llm(config, selected_llm_index=selected_model_idx)
    context = [load(doc) for doc in data.context]
    response = llm_respond(llm, data.prompt, context)
    return response


############
### Main ###
############
def main():
    uvicorn.run(
        "llm_service.main:app",
        host=config.get("host", "127.0.0.1"),
        port=config.get("port", 5000),
        log_level="info",
    )


if __name__ == "__main__":
    main()
