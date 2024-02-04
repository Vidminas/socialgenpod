import os
from urllib.parse import unquote
import requests

import streamlit as st
from st_pages import Page, show_pages, hide_pages
from langchain_core.chat_history import BaseChatMessageHistory

from chat_app.solid_message_history import SolidChatMessageHistory
from chat_app.solid_pod_utils import SolidPodUtils
from chat_app.apis.base_api import BaseEmbeddingsAPI, BaseLLMAPI
from chat_app.apis.demo_api import DemoEmbeddingsAPI, DemoLLMAPI

hostname = os.environ.get("WEBSITE_HOSTNAME")
if hostname is not None:
    OAUTH_CALLBACK_URI = f"https://{hostname}/callback"
else:
    OAUTH_CALLBACK_URI = "http://localhost:8501/callback"


def show_login_sidebar():
    from chat_app.solid_oidc_button import SolidOidcComponent

    # Default IDP list from https://solidproject.org/users/get-a-pod
    solid_server_url = st.sidebar.selectbox(
        "Solid ID Provider",
        (
            "https://solidcommunity.net/",
            "https://login.inrupt.com/",
            "https://solidweb.org/",
            "https://trinpod.us/",
            "https://get.use.id/",
            "https://solidweb.me/",
            "https://datapod.igrant.io/",
            "https://solid.redpencil.io/",
            "https://teamid.live/",
            "Other...",
        ),
        disabled="solid_token" in st.session_state,
    )
    if solid_server_url == "Other...":
        solid_server_url = st.sidebar.text_input(
            "Solid Server URL",
            "https://solidpod.azurewebsites.net",
            disabled="solid_token" in st.session_state,
        )

    if "solid_idps" not in st.session_state:
        st.session_state["solid_idps"] = {}

    if solid_server_url not in st.session_state["solid_idps"]:
        st.session_state["solid_idps"][solid_server_url] = SolidOidcComponent(
            solid_server_url
        )

    solid_client = st.session_state["solid_idps"][solid_server_url]

    with st.sidebar:
        result = solid_client.authorize_button(
            name="Login with Solid",
            icon="https://raw.githubusercontent.com/CommunitySolidServer/CommunitySolidServer/main/templates/images/solid.svg",
            redirect_uri=OAUTH_CALLBACK_URI,
            key="solid",
            height=670,
            width=850,
            use_container_width=True,
        )

        if result:
            st.session_state["solid_token"] = result["token"]
            st.rerun()


def show_config(solid_utils: SolidPodUtils):
    config = solid_utils.read_solid_item(solid_utils.config_uri)
    if len(config):
        return

    with st.form("reuse-config-form"):
        st.title("Reuse an existing configuration")
        st.text_input("Configuration file URI")
        st.form_submit_button("Import configuration")

    with st.form("new-config-form"):
        st.title("Or configure your chatbot service")
        col1, col2 = st.columns((2, 1))
        embeddings_provider = col1.text_input("Embeddings provider", "http://localhost:5000/")
        embeddings_api = col2.selectbox("Embeddings provider API", ("Demo", "OpenAI"))
        llm_provider = col1.text_input("LLM provider", "http://localhost:5000/")
        llm_api = col2.selectbox("LLM provider API", ("Demo", "OpenAI"))
        submitted = st.form_submit_button("Confirm")
        if submitted:
            try:
                res = requests.get(embeddings_provider)
                if not res.ok:
                    st.error("Error communicating with embeddings provider: " + res.text)
                    return
            except requests.exceptions.ConnectionError as e:
                st.error("Error communicating with embeddings provider: " + str(e))
                return

            try:
                res = requests.get(llm_provider)
                if not res.ok:
                    st.error("Error communicating with LLM provider: " + res.text)
                    return
            except requests.exceptions.ConnectionError as e:
                st.error("Error communicating with LLM provider: " + str(e))
                return
            
            if embeddings_api != "Demo" or llm_api != "Demo":
                st.error("Only demo APIs are supported for now")
                return
            st.session_state["provider_config"] = (DemoEmbeddingsAPI(embeddings_provider), DemoLLMAPI(llm_provider))
            

def show_chats_sidebar(solid_utils: SolidPodUtils):
    st.sidebar.markdown(f"Logged in as <{solid_utils.webid}>")

    def logout():
        # TODO: this should also revoke the token, but not implemented yet
        del st.session_state["solid_token"]
        st.session_state.pop("llm_options", None)
        st.session_state.pop("msg_history", None)

    st.sidebar.button("Log Out", on_click=logout)

    threads = solid_utils.list_container_items(solid_utils.workspace_uri)
    if "msg_history" not in st.session_state:
        st.session_state["msg_history"] = SolidChatMessageHistory(
            st.session_state["solid_token"],
            thread_uri=threads[0] if len(threads) else None,
        )

    def switch_active_thread(new_thread_uri):
        if new_thread_uri != st.session_state["msg_history"].thread_uri:
            st.session_state["msg_history"] = SolidChatMessageHistory(
                st.session_state["solid_token"], new_thread_uri
            )

    st.sidebar.divider()
    st.sidebar.caption("Chats")

    for thread in threads:
        thread_label = unquote(
            thread.removeprefix(solid_utils.workspace_uri).removesuffix(".ttl")
        )
        with st.sidebar:
            col1, col2 = st.columns([5, 1])
            col1.button(
                label=thread_label,
                key=thread,
                on_click=switch_active_thread,
                args=(thread,),
                type=(
                    "primary"
                    if thread == st.session_state["msg_history"].thread_uri
                    else "secondary"
                ),
                use_container_width=True,
            )
            col2.button(
                label=":wastebasket:",
                key="del_" + thread,
                help="Delete " + thread_label,
                on_click=st.session_state["msg_history"].clear,
            )
    if not len(threads):
        st.sidebar.write("Nothing here yet... Start typing on the right ->")
    st.sidebar.button(
        label="Start new conversation",
        on_click=switch_active_thread,
        args=(None,),
        use_container_width=True,
    )
    st.sidebar.divider()

def print_state_messages(history: BaseChatMessageHistory):
    roles = {
        "human": "user",
        "ai": "assistant",
    }

    for message in history.messages:
        with st.chat_message(roles[message.type]):
            st.markdown(message.content)


def main():
    st.set_page_config(page_title="Social Gen Pod", page_icon="🐢")
    show_pages(
        [
            Page("chat_app/main.py", "Social Gen Pod"),
            Page("chat_app/callback.py", "callback"),
        ]
    )
    hide_pages(["callback"])
    st.title("Social Gen Pod 🐢")
    st.sidebar.title("Options")

    if "solid_token" not in st.session_state:
        show_login_sidebar()
        return

    solid_utils = SolidPodUtils(st.session_state["solid_token"])
    show_chats_sidebar(solid_utils)

    if "provider_config" not in st.session_state:
        show_config(solid_utils)
        return
    embeddings_provider: BaseEmbeddingsAPI = st.session_state["provider_config"][0]
    llm_provider: BaseLLMAPI = st.session_state["provider_config"][1]
    
    st.sidebar.markdown(str(embeddings_provider))
    st.sidebar.markdown(str(llm_provider))
    def reset_config():
        del st.session_state["provider_config"]
    st.sidebar.button("Review configuration", on_click=reset_config)

    if "llm_options" not in st.session_state:
        st.session_state["llm_options"] = llm_provider.get_llm_models()
    selected_llm = st.sidebar.radio("LLM", st.session_state["llm_options"])

    if "msg_history" not in st.session_state:
        st.session_state["msg_history"] = SolidChatMessageHistory(
            st.session_state["solid_token"]
        )
    history = st.session_state["msg_history"]
    print_state_messages(history)

    if "input_disabled" not in st.session_state:
        st.session_state["input_disabled"] = False

    if prompt := st.chat_input(
        "Enter a query",
        disabled=st.session_state["input_disabled"],
        on_submit=lambda: st.session_state.update(input_disabled=True),
    ):
        with st.chat_message("user"):
            st.markdown(prompt)
        history.add_user_message(prompt)

        with st.spinner("LLM is thinking...."):
            ai_msg = llm_provider.chat_completion(selected_llm, history.messages)
        st.session_state["input_disabled"] = False
        history.add_ai_message(ai_msg)


def cli():
    import sys
    from pathlib import Path
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__))] + sys.argv[1:]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
