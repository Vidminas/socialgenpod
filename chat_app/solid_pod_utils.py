import requests
from rdflib import Namespace, RDF, URIRef, Graph
from solid_oidc_client import SolidAuthSession


APP_URI = "https://github.com/Vidminas/socialgenpod"
# https://solidproject.org/TR/protocol#namespaces
pim_ns = Namespace("http://www.w3.org/ns/pim/space#")
solid_ns = Namespace("http://www.w3.org/ns/solid/terms#")
ldp_ns = Namespace("http://www.w3.org/ns/ldp#")


def get_item_name(url: str) -> str:
    if url[-1] == "/":
        url = url[:-1]

    if url.count("/") == 2:  # is base url, no item name
        return ""

    i = url.rindex("/")
    return url[i + 1 :]


class SolidPodUtils:
    """
    A helper class for managing configuration and data in a Solid pod

    Args:
        solid_token: A serialized SolidAuthSession
    """

    def __init__(self, solid_token):
        self.solid_auth = SolidAuthSession.deserialize(solid_token)
        self.session = requests.Session()

        self.webid = self.solid_auth.get_web_id()
        profile_card_uri = self.webid.removesuffix("#me")
        profile_card = self.read_solid_item(profile_card_uri)

        # https://solid.github.io/webid-profile/#private-preferences
        preferences_file_uri = profile_card.value(
            subject=self.webid, predicate=pim_ns.preferencesFile
        )
        if preferences_file_uri is None:
            preferences_file_uri = self.webid.replace("card#me", "preferences.ttl")
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(self.webid).n3()} {pim_ns.preferencesFile.n3()} {URIRef(preferences_file_uri).n3()} .\n"
                f"}}"
            )
            self.update_solid_item(profile_card_uri, sparql)
        if not self.is_solid_item_available(preferences_file_uri):
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
            subject=self.webid, predicate=solid_ns.privateTypeIndex
        )
        if private_index_uri is None:
            private_index_uri = self.webid.replace(
                "profile/card#me", "settings/privateTypeIndex.ttl"
            )
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(self.webid).n3()} {solid_ns.privateTypeIndex.n3()} {URIRef(private_index_uri).n3()} .\n"
                f"}}"
            )
            self.update_solid_item(preferences_file_uri, sparql)
        if not self.is_solid_item_available(private_index_uri):
            self.create_solid_item(private_index_uri)
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(private_index_uri).n3()} {RDF.type.n3()} {solid_ns.TypeIndex.n3()} .\n"
                f"{URIRef(private_index_uri).n3()} {RDF.type.n3()} {solid_ns.UnlistedDocument.n3()} .\n"
                f"}}"
            )
            self.update_solid_item(private_index_uri, sparql)

        private_index = self.read_solid_item(private_index_uri)

        self.workspace_uri = private_index.value(
            subject=APP_URI, predicate=solid_ns.instanceContainer
        )
        if self.workspace_uri is None:
            self.workspace_uri = self.webid.replace(
                "profile/card#me", "private/genpod/"
            )
            sparql = (
                f"INSERT DATA {{\n"
                f"{URIRef(APP_URI).n3()} {RDF.type.n3()} {solid_ns.TypeRegistration.n3()} .\n"
                f"{URIRef(APP_URI).n3()} {solid_ns.forClass.n3()} {pim_ns.SharedWorkspace.n3()} .\n"
                f"{URIRef(APP_URI).n3()} {solid_ns.instance.n3()} {URIRef(self.workspace_uri).n3()} .\n"
                f"}}"
            )
            self.update_solid_item(private_index_uri, sparql)
        if not self.is_solid_item_available(self.workspace_uri):
            self.create_solid_item(self.workspace_uri)

    def is_solid_item_available(self, url) -> bool:
        try:
            res = self.session.head(
                url,
                headers=self.solid_auth.get_auth_headers(url, "HEAD"),
                allow_redirects=True,
            )
            return res.ok
        except requests.exceptions.ConnectionError:
            return False

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
    
    def read_solid_item(self, uri) -> Graph:
        content = Graph()
        content.bind("solid", solid_ns)
        content.bind("pim", pim_ns)
        content.bind("ldp", ldp_ns)
        res = self.session.get(
            uri,
            headers={
                "Content-Type": "text/turtle",
                **self.solid_auth.get_auth_headers(uri, "GET"),
            },
        )
        content.parse(data=res.text, publicID=uri)
        return content

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

    def delete_solid_item(self, uri: str):
        res = self.session.delete(
            uri,
            headers=self.solid_auth.get_auth_headers(uri, "DELETE"),
        )
        return res.ok
