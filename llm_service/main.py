from fastapi import FastAPI, Depends, Header, Request, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import Optional
from langchain.schema import messages_from_dict

from .chains import make_conversation_chain
from .config import get_config
from .solid_utils import attessPossession

app = FastAPI()
config = get_config()


class ChatCompletionRequestData(BaseModel):
    model: str
    messages: list[dict]


def as_header(cls):
    """decorator for pydantic model
    replaces the Signature of the parameters of the pydantic model with `Header`
    See https://github.com/tiangolo/fastapi/issues/2915
    """
    cls.__signature__ = cls.__signature__.replace(
        parameters=[
            arg.replace(
                default=Header(...) if arg.default is arg.empty else Header(arg.default)
            )
            for arg in cls.__signature__.parameters.values()
        ]
    )
    return cls


@as_header
class WebIdDPoPInfoHeader(BaseModel):
    authorization: str
    dpop: str
    x_forwarded_host: Optional[str]
    x_forwarded_protocol: Optional[str]
    webid: Optional[str]


def checkIdentity(request: Request, hdrs: WebIdDPoPInfoHeader):
    method = 'POST'
    host = hdrs.x_forwarded_host or request.url.hostname  # Use X-Forwarded-For in case there is a reverse proxy in-between the client and the server
    protocol = hdrs.x_forwarded_protocol or request.url.scheme  # Same as above
    path_prefix = '/'  # Needed if deployed to a (sub)path instead of root of the hostname
    request_url = f"{protocol}://{host}{path_prefix}{request.url.path}"
    return attessPossession(hdrs.authorization, hdrs.dpop, method, request_url, hdrs.webid)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/models/")
def get_models() -> list[str]:
    return list(map(lambda llm: llm.get("model"), config["llms"]))


@app.post("/embeddings/")
def create_embeddings():
    pass


# curl https://api.openai.com/v1/embeddings \
#   -H "Authorization: Bearer $OPENAI_API_KEY" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "input": "The food was delicious and the waiter...",
#     "model": "text-embedding-ada-002",
#     "encoding_format": "float"
#   }'

# {
#   "object": "list",
#   "data": [
#     {
#       "object": "embedding",
#       "embedding": [
#         0.0023064255,
#         -0.009327292,
#         .... (1536 floats total for ada-002)
#         -0.0028842222,
#       ],
#       "index": 0
#     }
#   ],
#   "model": "text-embedding-ada-002",
#   "usage": {
#     "prompt_tokens": 8,
#     "total_tokens": 8
#   }
# }


@app.post("/completions/")
def chat_completion(req: ChatCompletionRequestData, request: Request, hdrs: WebIdDPoPInfoHeader = Depends(WebIdDPoPInfoHeader)) -> str:
    if not checkIdentity(request):
        raise HTTPException(400, detail='WebID attestation failed')

    selected_model_idx = -1
    for idx, llm in enumerate(config["llms"]):
        if llm["model"] == req.model:
            selected_model_idx = idx
            break

    messages = messages_from_dict(req.messages)

    if selected_model_idx != -1:
        llm = make_conversation_chain(config, selected_llm_index=selected_model_idx)
        response = llm.invoke(
            {"question": messages[-1].content, "chat_history": messages[:-1]},
            # callbacks=[retrieve_callback, print_callback, stdout_callback],
        )
        return response["answer"]
    else:
        return ""


def main():
    uvicorn.run(
        "llm_service.main:app",
        host=config.get("host", "127.0.0.1"),
        port=config.get("port", 5000),
        log_level="info",
    )


if __name__ == "__main__":
    main()
