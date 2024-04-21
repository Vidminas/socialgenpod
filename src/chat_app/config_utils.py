from rdflib import Graph, URIRef, Namespace, FOAF

from chat_app.solid_pod_utils import SolidPodUtils

ldp_ns = Namespace("http://www.w3.org/ns/ldp#")


def read_config(
    solid_utils: SolidPodUtils,
    default_retrieval_service: str,
    default_llm_service: str,
    default_docs_location: str,
):
    config = solid_utils.read_solid_item(solid_utils.config_uri)
    if (
        config_retrieval_service := config.value(
            subject=URIRef(f"{solid_utils.config_uri}#retrieval_service"),
            predicate=FOAF.accountServiceHomepage,
        )
    ) is not None:
        default_retrieval_service = config_retrieval_service
    if (
        config_llm_service := config.value(
            subject=URIRef(f"{solid_utils.config_uri}#llm_service"),
            predicate=FOAF.accountServiceHomepage,
        )
    ) is not None:
        default_llm_service = config_llm_service
    if (
        config_docs_location := config.value(
            subject=URIRef(f"{solid_utils.config_uri}#docs_location"),
            predicate=ldp_ns.Resource,
        )
    ) is not None:
        default_docs_location = config_docs_location

    return default_retrieval_service, default_llm_service, default_docs_location


def write_config(
    solid_utils: SolidPodUtils,
    retrieval_service: str,
    llm_service: str,
    docs_location: str,
):
    delete_wheres = []
    inserts = []
    if retrieval_service:
        retrieval_service_node = URIRef(f"{solid_utils.config_uri}#retrieval_service")
        delete_wheres.append(
            f"{retrieval_service_node.n3()} {FOAF.accountServiceHomepage.n3()} ?uri"
        )
        inserts.append(
            f"{retrieval_service_node.n3()} {FOAF.accountServiceHomepage.n3()} <{retrieval_service}>"
        )
    if llm_service:
        llm_service_node = URIRef(f"{solid_utils.config_uri}#llm_service")
        delete_wheres.append(
            f"{llm_service_node.n3()} {FOAF.accountServiceHomepage.n3()} ?uri"
        )
        inserts.append(
            f"{llm_service_node.n3()} {FOAF.accountServiceHomepage.n3()} <{llm_service}>"
        )
    if docs_location:
        docs_location_node = URIRef(f"{solid_utils.config_uri}#docs_location")
        delete_wheres.append(f"{docs_location_node.n3()} {ldp_ns.Resource.n3()} ?uri")
        inserts.append(
            f"{docs_location_node.n3()} {ldp_ns.Resource.n3()} <{docs_location}>"
        )

    delete_wheres = " .\n".join(delete_wheres)
    solid_utils.update_solid_item(solid_utils.config_uri, f"DELETE WHERE {{ {delete_wheres} }}")

    inserts = " .\n".join(inserts)
    solid_utils.update_solid_item(solid_utils.config_uri, f"INSERT DATA {{ {inserts} }}")
