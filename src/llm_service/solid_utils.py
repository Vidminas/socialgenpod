from collections import deque
from functools import cache
import os
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Depends, Header, Request, HTTPException
from pydantic import BaseModel
from rdflib import Namespace, RDF, URIRef, Graph
import requests
from dotenv import load_dotenv
from solid_client_credentials import SolidClientCredentialsAuth, DpopTokenProvider


class ClientCredentials:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret


class CommunitySolidServer:
    def __init__(self, base_url: str):
        self.base_url = base_url

    class CssAccount:
        def __init__(
            self,
            css_base_url: str,
            name: str,
            email: str,
            password: str,
            web_id: str,
            pod_base_url: str,
        ) -> None:
            self.css_base_url = css_base_url
            self.name = name
            self.email = email
            self.password = password
            self.web_id = web_id
            self.pod_base_url = pod_base_url

    def create_css_account(self, name: str, email: str, password: str) -> CssAccount:
        register_endpoint = f"{self.base_url}/idp/register/"

        res = requests.post(
            register_endpoint,
            json={
                "createWebId": "on",
                "webId": "",
                "register": "on",
                "createPod": "on",
                "podName": name,
                "email": email,
                "password": password,
                "confirmPassword": password,
            },
            timeout=5000,
        )

        if not res.ok:
            raise Exception(f"Could not create account: {res.status_code} {res.text}")

        data = res.json()
        account = CommunitySolidServer.CssAccount(
            css_base_url=self.base_url,
            name=name,
            email=email,
            password=password,
            web_id=data["webId"],
            pod_base_url=data["podBaseUrl"],
        )
        return account

    def get_client_credentials(self, account: CssAccount) -> ClientCredentials:
        credentials_endpoint = f"{account.css_base_url}/idp/credentials/"

        res = requests.post(
            credentials_endpoint,
            json={
                "name": "socialgenpod-client-credentials",
                "email": account.email,
                "password": account.password,
            },
            timeout=5000,
        )

        if not res.ok:
            raise Exception(
                f"Could not create client credentials: {res.status_code} {res.text}"
            )

        data = res.json()
        return ClientCredentials(client_id=data["id"], client_secret=data["secret"])


@cache
def register_retrieval_service() -> requests.Session:
    load_dotenv()
    server = CommunitySolidServer(os.environ.get("RETRIEVAL_SERVICE_IDP"))
    name = os.environ.get("RETRIEVAL_SERVICE_NAME")
    email = os.environ.get("RETRIEVAL_SERVICE_EMAIL")
    password = os.environ.get("RETRIEVAL_SERVICE_PASSWORD")
    webid = os.environ.get("RETRIEVAL_SERVICE_WEBID")
    if name is None or email is None or password is None or webid is None:
        raise RuntimeError(
            f"One or more retrieval service environment variables are not configured!\n"
            f"{name = }, {email = }, {password = }, {webid = }"
        )

    try:
        account = server.create_css_account(name, email, password)
    except:
        account = CommunitySolidServer.CssAccount(
            css_base_url=server.base_url,
            name=name,
            email=email,
            password=password,
            web_id=webid,
            pod_base_url="",
        )

    client_credentials = server.get_client_credentials(account)
    token_provider = DpopTokenProvider(
        issuer_url=server.base_url,
        client_id=client_credentials.client_id,
        client_secret=client_credentials.client_secret,
    )
    session = requests.Session()
    session.auth = SolidClientCredentialsAuth(token_provider)
    return session


ldp_ns = Namespace("http://www.w3.org/ns/ldp#")
session = register_retrieval_service()


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


def discover_document_uris(base_uri: str) -> list[str]:
    found_uris = []

    worklist = deque([base_uri])
    while len(worklist):
        uri = worklist.popleft()
        res = session.head(
            uri,
            allow_redirects=True,
        )

        if res.headers.get("Content-Type", None) != "text/turtle":
            # not an RDF resource, so don't look inside
            found_uris.append(uri)
            continue

        if ldp_ns.BasicContainer.n3() not in res.headers.get("Link", ""):
            # not a Solid container, so don't look inside
            found_uris.append(uri)
            continue

        # otherwise it is a container, so explore all included resources
        content = Graph()
        content.bind("ldp", ldp_ns)
        res = session.get(
            uri,
            headers={
                "Content-Type": "text/turtle",
            },
        )
        content.parse(data=res.text, publicID=uri)
        worklist.extend(content.objects(URIRef(uri), ldp_ns.contains, unique=True))

    return found_uris


def get_item_name(url: str) -> str:
    if url[-1] == "/":
        url = url[:-1]

    if url.count("/") == 2:  # is base url, no item name
        return "index.ttl"

    i = url.rindex("/")
    return url[i + 1 :]


def download_resource(uri: str, save_dir: str):
    res = session.get(uri, stream=True)
    filename = get_item_name(uri)

    with open(os.path.join(save_dir, filename), mode="wb") as f:
        for chunk in res.iter_content(chunk_size=2048):
            if chunk:
                f.write(chunk)


def webid_to_filepath(webid: str) -> str:
    p = urlparse(webid)
    webid_root = p.path
    if webid_root.count("/", 1) > 0:
        webid_root = webid_root[: webid_root.find("/", 1)]
    return p.netloc + webid_root


def check_uri_access(uri: str) -> bool:
    res = session.get(uri)
    return res.ok
