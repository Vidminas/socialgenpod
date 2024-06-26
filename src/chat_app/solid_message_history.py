from urllib.parse import quote

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from rdflib import Graph, BNode, URIRef, Literal, RDF, XSD, SDO, PROF
from rdflib.collection import Collection

from chat_app.solid_pod_utils import SolidPodUtils


class SolidChatMessageHistory(BaseChatMessageHistory):
    """
    Chat message history that stores messages in a Solid pod.

    Args:
        solid_token: A serialized SolidAuthSession
    """

    def __init__(self, solid_token, thread_uri=None):
        self.graph = Graph()
        self.solid_utils = SolidPodUtils(solid_token)
        self.thread_uri = thread_uri

    @property
    def messages(self) -> list[BaseMessage]:
        """Retrieve the current list of messages"""
        if self.thread_uri is None:
            return []

        if not self.solid_utils.is_solid_item_available(self.thread_uri):
            self.solid_utils.create_solid_item(self.thread_uri)

        self.graph = self.solid_utils.read_solid_item(self.thread_uri)
        conversation = self.graph.value(predicate=RDF.type, object=SDO.Conversation)
        if conversation is None:
            return []

        rdf_list = Collection(
            self.graph, self.graph.value(subject=conversation, predicate=SDO.hasPart)
        )
        msgs = [
            BaseMessage(
                content=self.graph.value(
                    subject=msg, predicate=PROF.hasResource
                ).toPython(),
                type=self.graph.value(subject=msg, predicate=PROF.hasRole).toPython(),
            )
            for msg in rdf_list
        ]
        return msgs

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the session memory"""
        if self.thread_uri is None:
            thread_name = quote(
                " ".join(message.content.split(maxsplit=3)[:3]), safe=""
            )
            candidate_uri = self.solid_utils.workspace_uri + thread_name + ".ttl"
            i = 2
            while self.solid_utils.is_solid_item_available(candidate_uri):
                candidate_uri = (
                    self.solid_utils.workspace_uri + thread_name + f" #{i}.ttl"
                )
                i += 1
            self.thread_uri = candidate_uri
            self.solid_utils.create_solid_item(self.thread_uri)

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

        msgs_node = self.graph.value(predicate=RDF.type, object=SDO.Conversation)
        if msgs_node is None:
            msgs_node = URIRef(f"{self.thread_uri}#messages")
            update_graph.add((msgs_node, RDF.type, SDO.Conversation))

            first_list_node = BNode()
            update_graph.add((first_list_node, RDF.type, RDF.List))
            update_graph.add((first_list_node, RDF.first, msg))
            update_graph.add((first_list_node, RDF.rest, RDF.nil))

            update_graph.add((msgs_node, SDO.hasPart, first_list_node))
            update_graph.add((first_list_node, SDO.isPartOf, msgs_node))

            triples = "\n".join(
                [
                    f"{subject.n3()} {predicate.n3()} {object.n3()} ."
                    for subject, predicate, object in update_graph
                ]
            )
            sparql = f"INSERT DATA {{{triples}}}"
        else:
            new_item = BNode()
            update_graph.add((new_item, RDF.type, RDF.List))
            update_graph.add((new_item, RDF.first, msg))
            update_graph.add((new_item, RDF.rest, RDF.nil))

            triples = "\n".join(
                [
                    f"{subject.n3()} {predicate.n3()} {object.n3()} ."
                    for subject, predicate, object in update_graph
                ]
            )
            sparql = f"""
                DELETE {{ ?end {RDF.rest.n3()} {RDF.nil.n3()} }}
                INSERT {{ ?end {RDF.rest.n3()} {new_item.n3()} .\n
                          {triples} }}
                WHERE {{ ?end  {RDF.rest.n3()} {RDF.nil.n3()} }}
            """

        # Update remote copy
        self.solid_utils.update_solid_item(self.thread_uri, sparql)
        # Update local copy
        self.graph.update(sparql)

    def clear(self) -> None:
        """Clear session memory"""
        self.solid_utils.delete_solid_item(self.thread_uri)
        self.thread_uri = None
        self.graph = Graph()
