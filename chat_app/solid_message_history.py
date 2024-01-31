import requests

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from rdflib import Graph
from rdflib.term import BNode, URIRef, Literal
from rdflib.namespace import RDF, PROF, XSD
from rdflib.collection import Collection
from solid_oidc_client import SolidAuthSession


def get_item_name(url: str) -> str:
    if url[-1] == "/":
        url = url[:-1]

    if url.count("/") == 2:  # is base url, no item name
        return ""

    i = url.rindex("/")
    return url[i + 1 :]


class SolidChatMessageHistory(BaseChatMessageHistory):
    """
    Chat message history that stores messages in a Solid pod.

    Args:
        solid_token: A serialized SolidAuthSession
    """

    def __init__(self, solid_token):
        self.solid_auth = SolidAuthSession.deserialize(solid_token)
        self.pod_base_url = self.solid_auth.get_web_id().replace("profile/card#me", "")
        self.session = requests.Session()
        self.graph = Graph()

    def is_item_available(self, url) -> bool:
        try:
            res = self.session.head(
                url,
                headers=self.solid_auth.get_auth_headers(url, "HEAD"),
                allow_redirects=True,
            )
            return res.ok
        except requests.exceptions.ConnectionError:
            return False

    def create_item(self, url: str) -> bool:
        res = self.session.put(
            url,
            data=None,
            headers={
                "Accept": "text/turtle",
                "If-None-Match": "*",
                "Link": '<http://www.w3.org/ns/ldp#BasicContainer>; rel="type"'
                if url.endswith("/")
                else '<http://www.w3.org/ns/ldp#Resource>; rel="type"',
                "Slug": get_item_name(url),
                "Content-Type": "text/turtle",
                **self.solid_auth.get_auth_headers(url, "PUT"),
            },
        )
        return res.ok

    @property
    def messages(self) -> list[BaseMessage]:
        """Retrieve the current list of messages"""

        if not self.is_item_available(f"{self.pod_base_url}private/"):
            self.create_item(f"{self.pod_base_url}private/")
        if not self.is_item_available(f"{self.pod_base_url}private/chatdocs.ttl"):
            self.create_item(f"{self.pod_base_url}private/chatdocs.ttl")

        res = self.session.get(
            f"{self.pod_base_url}private/chatdocs.ttl",
            headers=self.solid_auth.get_auth_headers(
                f"{self.pod_base_url}private/chatdocs.ttl", "GET"
            ),
        )
        if not res.ok:
            print("getting messages failed", res.text)
            msgs = []
        else:
            self.graph.parse(
                data=res.text, publicID=f"{self.pod_base_url}private/chatdocs.ttl"
            )
            list_node = self.graph.value(predicate=RDF.type, object=RDF.List)
            if list_node is None:
                return []

            rdf_list = Collection(self.graph, list_node)
            msgs = [
                BaseMessage(
                    content=self.graph.value(
                        subject=msg, predicate=PROF.hasResource
                    ).toPython(),
                    type=self.graph.value(
                        subject=msg, predicate=PROF.hasRole
                    ).toPython(),
                )
                for msg in rdf_list
            ]
        return msgs

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the session memory"""
        # https://solidproject.org/TR/protocol#n3-patch seems to be broken with Community Solid Server
        # https://www.w3.org/TR/sparql11-update/ works
        update_graph = Graph()

        msg = BNode()
        update_graph.add((msg, RDF.type, PROF.ResourceDescriptor))
        update_graph.add(
            (msg, PROF.hasResource, Literal(message.content, datatype=XSD.string))
        )
        update_graph.add(
            (msg, PROF.hasRole, Literal(message.type, datatype=XSD.string))
        )

        list_node = self.graph.value(predicate=RDF.type, object=RDF.List)
        if list_node is None:
            msgs_node = URIRef(f"{self.pod_base_url}private/chatdocs.ttl#messages")
            update_graph.add((msgs_node, RDF.type, RDF.List))

            msgs = Collection(update_graph, msgs_node)
            msgs.append(msg)

            triples = "\n".join(
                [
                    f"{subject.n3()} {predicate.n3()} {object.n3()} ."
                    for subject, predicate, object in update_graph
                ]
            )
            sparql = f"INSERT DATA {{{triples}}}"
        else:
            new_item = BNode()
            update_graph.add((new_item, RDF.first, msg))
            update_graph.add((new_item, RDF.rest, RDF.nil))

            triples = "\n".join(
                [
                    f"{subject.n3()} {predicate.n3()} {object.n3()} ."
                    for subject, predicate, object in update_graph
                ]
            )
            sparql = f"""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                DELETE {{ ?end rdf:rest rdf:nil }}
                INSERT {{ ?end rdf:rest {new_item.n3()} .\n
                          {triples} }}
                WHERE {{ ?end  rdf:rest  rdf:nil }}
            """

        # Update remote copy
        self.session.patch(
            url=f"{self.pod_base_url}private/chatdocs.ttl",
            data=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-update",
                **self.solid_auth.get_auth_headers(
                    f"{self.pod_base_url}private/chatdocs.ttl", "PATCH"
                ),
            },
        )
        # Update local copy
        self.graph.update(sparql)

    def clear(self) -> None:
        """Clear session memory"""
        self.session.delete(
            f"{self.pod_base_url}private/chatdocs.ttl",
            headers=self.solid_auth.get_auth_headers(
                f"{self.pod_base_url}private/chatdocs.ttl", "DELETE"
            ),
        )
        self.graph = Graph()
