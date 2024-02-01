import os
import requests
import streamlit as st
from st_pages import Page, show_pages, hide_pages
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.schema import messages_to_dict
from chat_app.solid_message_history import SolidChatMessageHistory

print("WEBSITE_SITE_NAME", os.environ.get("WEBSITE_SITE_NAME"))
print("WEBSITE_HOSTNAME", os.environ.get("WEBSITE_HOSTNAME"))
print("SERVER_PORT", os.environ.get("SERVER_PORT"))
print("PORT", os.environ.get("PORT"))
print("WEBSITES_PORT", os.environ.get("WEBSITES_PORT"))

OAUTH_CALLBACK_URI = "http://localhost:8501/callback"


def setup_login_sidebar():
    from chat_app.solid_oidc_button import SolidOidcComponent
    from solid_oidc_client import SolidAuthSession

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
        solid_auth = SolidAuthSession.deserialize(st.session_state["solid_token"])
        st.sidebar.markdown(f"Logged in as <{solid_auth.get_web_id()}>")

        def logout():
            # TODO: this should also revoke the token, but not implemented yet
            del st.session_state["solid_token"]
            st.session_state.pop("llm_options", None)
            st.session_state.pop("msg_history", None)

        st.sidebar.button("Log Out", on_click=logout)


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
    st.set_page_config(page_title="Social Gen Pod", page_icon="🐢")
    show_pages([
        Page("chat_app/main.py", "Social Gen Pod"),
        Page("chat_app/callback.py", "callback"),
    ])
    hide_pages(["callback"])
    st.title("Social Gen Pod 🐢")
    st.sidebar.title("Options")
    setup_login_sidebar()

    if "solid_token" in st.session_state:
        if "msg_history" not in st.session_state:
            st.session_state["msg_history"] = SolidChatMessageHistory(
                st.session_state["solid_token"]
            )
        history = st.session_state["msg_history"]
        init_messages(history)
        print_state_messages(history)

        if "llm_options" not in st.session_state:
            response = requests.get("http://localhost:5000/models/")
            st.session_state["llm_options"] = response.json()
        selected_llm = st.sidebar.radio("LLM", st.session_state["llm_options"])

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
                response = requests.post(
                    "http://localhost:5000/completions/",
                    json={
                        "model": selected_llm,
                        "messages": messages_to_dict(history.messages),
                    },
                )
            st.session_state["input_disabled"] = False
            if not response.ok:
                raise RuntimeError(response.text)
            else:
                history.add_ai_message(response.text)
                st.rerun()


def cli():
    import sys
    from pathlib import Path
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__))] + sys.argv[1:]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
