import streamlit as st

from chat_app.solid import solid_login


def main():
    st.set_page_config(page_title="Solid RAG", page_icon="🐢")
    st.title("Solid RAG")
    st.sidebar.title("Options")

    # Default IDP list from https://solidproject.org/users/get-a-pod
    solid_server_url = st.sidebar.selectbox("Solid ID Provider", (
        "https://solidcommunity.net/",
        "https://start.inrupt.com/",
        "https://solidweb.org/",
        "https://trinpod.us/",
        "https://get.use.id/",
        "https://solidweb.me/",
        "https://datapod.igrant.io/",
        "https://solid.redpencil.io/",
        "https://teamid.live/",
        "Other..."
    ))
    if solid_server_url == "Other...":
        solid_server_url = st.sidebar.text_input("Solid Server URL", "https://solidpod.azurewebsites.net")

    logged_in = False
    if not logged_in:
        st.sidebar.button("Login", on_click=solid_login, args=(solid_server_url,))

    if prompt := st.chat_input("Enter a query"):
        with st.chat_message("user"):
            st.markdown(prompt)


def cli():
    import sys
    from pathlib import Path
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__))] + sys.argv[1:]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
