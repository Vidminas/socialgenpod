from typing import Union

from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

def main():
    uvicorn.run("llm_service.main:app", port=5000, log_level="info")

if __name__ == "__main__":
    main()