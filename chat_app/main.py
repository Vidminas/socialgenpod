import urllib.parse

import streamlit as st
from langchain_core.chat_history import BaseChatMessageHistory
from chat_app.solid_message_history import SolidChatMessageHistory


def setup_login_sidebar():
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
    )
    if solid_server_url == "Other...":
        solid_server_url = st.sidebar.text_input(
            "Solid Server URL", "https://solidpod.azurewebsites.net"
        )

    if "solid_idps" not in st.session_state:
        st.session_state["solid_idps"] = {}
        session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
        st.session_state["OAUTH_CALLBACK_URI"] = urllib.parse.urlunparse(
            [
                session.client.request.protocol,
                session.client.request.host,
                "",
                "",
                "",
                "",
            ]
        )

    OAUTH_CALLBACK_URI = st.session_state["OAUTH_CALLBACK_URI"]

    if solid_server_url not in st.session_state["solid_idps"]:
        st.session_state["solid_idps"][solid_server_url] = SolidOidcComponent(
            solid_server_url, [OAUTH_CALLBACK_URI]
        )

    solid_client = st.session_state["solid_idps"][solid_server_url]

    if "solid_token" not in st.session_state:
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
    else:
        st.markdown("Logged in!")

def init_messages(history: BaseChatMessageHistory) -> None:
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    if clear_button or len(history.messages) == 0:
        history.clear()


def print_state_messages(history: BaseChatMessageHistory):
    roles = {
        "human": "user",
        "ai": "assistant",
    }

    for message in history.messages:
        with st.chat_message(roles[message.type]):
            st.markdown(message.content)


def main():
    st.set_page_config(page_title="Solid RAG", page_icon="🐢")
    st.title("Solid RAG 🐢")
    st.sidebar.title("Options")
    setup_login_sidebar()

    if "solid_token" in st.session_state:
        if "msg_history" not in st.session_state:
            st.session_state["msg_history"] = SolidChatMessageHistory(st.session_state["solid_token"])
        history = st.session_state["msg_history"]

        init_messages(history)
        print_state_messages(history)
        
        if prompt := st.chat_input("Enter a query"):
            with st.chat_message("user"):
                st.markdown(prompt)
            history.add_user_message(prompt)


def cli():
    import sys
    from pathlib import Path
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__))] + sys.argv[1:]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
