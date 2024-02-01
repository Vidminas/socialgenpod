import requests

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from rdflib import Graph
from rdflib.term import BNode, URIRef, Literal
from rdflib.namespace import Namespace, RDF, PROF, XSD
from rdflib.collection import Collection
from solid_oidc_client import SolidAuthSession

# https://solidproject.org/TR/protocol#namespaces
pim_ns = Namespace("http://www.w3.org/ns/pim/space#")
solid_ns = Namespace("http://www.w3.org/ns/solid/terms#")
ldp_ns = Namespace("http://www.w3.org/ns/ldp#")
APP_URI = "https://github.com/Vidminas/socialgenpod"


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
        self.session = requests.Session()
        self.graph = Graph()

        webid = self.solid_auth.get_web_id()
        profile_card_uri = webid.removesuffix("#me")
        profile_card = self.read_solid_item(profile_card_uri)

        # https://solid.github.io/webid-profile/#private-preferences
        preferences_file_uri = profile_card.value(
            subject=webid, predicate=pim_ns.preferencesFile
        )
        if preferences_file_uri is None:
            preferences_file_uri = webid.replace("card#me", "preferences.ttl")
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(webid).n3()} {pim_ns.preferencesFile.n3()} {URIRef(preferences_file_uri).n3()} .\n"
                f"}}"
            )
            self.update_solid_item(profile_card_uri, sparql)
        if not self.is_item_available(preferences_file_uri):
            self.create_solid_item(preferences_file_uri)
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(preferences_file_uri).n3()} {RDF.type.n3()} {pim_ns.ConfigurationFile.n3()} .\n"
                f"}}"
            )
            self.update_solid_item(preferences_file_uri, sparql)

        preferences_file = self.read_solid_item(preferences_file_uri)

        # https://solid.github.io/type-indexes/#private-type-index
        private_index_uri = preferences_file.value(
            subject=webid, predicate=solid_ns.privateTypeIndex
        )
        if private_index_uri is None:
            private_index_uri = webid.replace(
                "profile/card#me", "settings/privateTypeIndex.ttl"
            )
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(webid).n3()} {solid_ns.privateTypeIndex.n3()} {URIRef(private_index_uri).n3()} .\n"
                f"}}"
            )
            self.update_solid_item(preferences_file_uri, sparql)
        if not self.is_item_available(private_index_uri):
            self.create_solid_item(private_index_uri)
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(private_index_uri).n3()} {RDF.type.n3()} {solid_ns.TypeIndex.n3()} .\n"
                f"{URIRef(private_index_uri).n3()} {RDF.type.n3()} {solid_ns.UnlistedDocument.n3()} .\n"
                f"}}"
            )
            self.update_solid_item(private_index_uri, sparql)

        private_index = self.read_solid_item(private_index_uri)

        genpod_workspace_uri = private_index.value(
            subject=APP_URI, predicate=solid_ns.instanceContainer
        )
        if genpod_workspace_uri is None:
            genpod_workspace_uri = webid.replace(
                "profile/card#me", "private/genpod/"
            )
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(APP_URI).n3()} {RDF.type.n3()} {solid_ns.TypeRegistration.n3()} .\n"
                f"{URIRef(APP_URI).n3()} {solid_ns.forClass.n3()} {pim_ns.SharedWorkspace.n3()} .\n"
                f"{URIRef(APP_URI).n3()} {solid_ns.instance.n3()} {URIRef(genpod_workspace_uri).n3()} .\n"
                f"}}"
            )
            self.update_solid_item(private_index_uri, sparql)
        if not self.is_item_available(genpod_workspace_uri):
            self.create_solid_item(genpod_workspace_uri)

        self.genpod_messages_uri = genpod_workspace_uri + "genpod.ttl"

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

    def read_solid_item(self, uri) -> Graph:
        content = Graph()
        content.bind("solid", solid_ns)
        content.bind("pim", pim_ns)
        res = self.session.get(
            uri,
            headers={
                "Content-Type": "text/turtle",
                **self.solid_auth.get_auth_headers(uri, "GET"),
            },
        )
        content.parse(data=res.text, publicID=uri)
        return content

    def create_solid_item(self, uri: str) -> bool:
        res = self.session.put(
            uri,
            data=None,
            headers={
                "Accept": "text/turtle",
                "If-None-Match": "*",
                "Link": f'{ldp_ns.BasicContainer.n3()}; rel="type"'
                if uri.endswith("/")
                else f'{ldp_ns.Resource.n3()}; rel="type"',
                "Slug": get_item_name(uri),
                "Content-Type": "text/turtle",
                **self.solid_auth.get_auth_headers(uri, "PUT"),
            },
        )
        return res.ok

    def update_solid_item(self, uri: str, sparql: str):
        res = self.session.patch(
            url=uri,
            data=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-update",
                **self.solid_auth.get_auth_headers(uri, "PATCH"),
            },
        )
        return res.ok

    @property
    def messages(self) -> list[BaseMessage]:
        """Retrieve the current list of messages"""
        if not self.is_item_available(self.genpod_messages_uri):
            self.create_solid_item(self.genpod_messages_uri)

        res = self.session.get(
            self.genpod_messages_uri,
            headers=self.solid_auth.get_auth_headers(self.genpod_messages_uri, "GET"),
        )
        if not res.ok:
            print("getting messages failed", res.text)
            msgs = []
        else:
            self.graph.parse(data=res.text, publicID=self.genpod_messages_uri)
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
            msgs_node = URIRef(f"{self.genpod_messages_uri}#messages")
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
            url=self.genpod_messages_uri,
            data=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-update",
                **self.solid_auth.get_auth_headers(self.genpod_messages_uri, "PATCH"),
            },
        )
        # Update local copy
        self.graph.update(sparql)

    def clear(self) -> None:
        """Clear session memory"""
        self.session.delete(
            self.genpod_messages_uri,
            headers=self.solid_auth.get_auth_headers(
                self.genpod_messages_uri, "DELETE"
            ),
        )
        self.graph = Graph()
