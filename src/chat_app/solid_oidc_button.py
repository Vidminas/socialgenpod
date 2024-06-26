import os
import json
from pathlib import Path
import urllib.parse
import requests

import streamlit as st
from solid_oidc_client import SolidOidcClient, MemStore, SolidAuthSession
from solid_oidc_client.solid_oidc_client import create_verifier_challenge
from solid_oidc_client.dpop_utils import create_dpop_token
from oic.oic import Client as OicClient
import jwcrypto.jwk
from streamlit_oauth import (
    OAuth2Component,
    StreamlitOauthError,
    _generate_state,
    _authorize_button,
)


@st.cache_data(ttl=300)
def generate_pkce_pair(client_id):
    # client_id is not used but required to cache separate pkce pairs for different clients
    return create_verifier_challenge()


@st.cache_data()
def get_hostname_uri():
    hostname = os.environ.get("WEBSITE_HOSTNAME")
    if hostname is not None:
        return f"https://{hostname}"
    else:
        return "http://localhost:8501"


@st.cache_data()
def get_callback_uri():
    OAUTH_CALLBACK_URI = f"{get_hostname_uri()}/callback"
    print(f"Auth endpoint set to {OAUTH_CALLBACK_URI}")
    return OAUTH_CALLBACK_URI


class SolidOidcComponent(OAuth2Component):
    def __init__(self, solid_server_url: str):
        self.client_id = "https://raw.githubusercontent.com/Vidminas/socialgenpod/main/src/chat_app/data/client_id.json"
        self.client_secret = None

        client = SolidOidcClient(storage=MemStore())
        client.client = OicClient(
            client_id=self.client_id,
            requests_dir=solid_server_url,
        )
        client.provider_info = client.client.provider_config(solid_server_url)

        metadata_path = Path(__file__).parent / "data/client_id.json"
        with metadata_path.open() as f:
            client_metadata = json.load(f)

        if (
            "none" not in client.provider_info["token_endpoint_auth_methods_supported"]
            or get_callback_uri() not in client_metadata["redirect_uris"]
            or get_hostname_uri() not in client_metadata["post_logout_redirect_uris"]
        ):
            # can't use public client, must register with server
            self.dynamic_client_register(client, client_metadata)

        super().__init__(
            client_id=None,
            client_secret=None,
            authorize_endpoint=None,
            token_endpoint=None,
            refresh_token_endpoint=None,
            revoke_token_endpoint=None,
            client=client,
        )

    def dynamic_client_register(self, client: SolidOidcClient, client_metadata: dict):
        if get_callback_uri() not in client_metadata["redirect_uris"]:
            client_metadata["redirect_uris"].append(get_callback_uri())
        if get_hostname_uri() not in client_metadata["post_logout_redirect_uris"]:
            client_metadata["post_logout_redirect_uris"].append(get_hostname_uri())
        registration_response = client.client.register(
            client.provider_info["registration_endpoint"],
            **client_metadata,
        )
        self.client_id = registration_response["client_id"]
        self.client_secret = registration_response["client_secret"]

    def create_login_uri(self, state, extras_params):
        code_verifier, code_challenge = generate_pkce_pair(self.client.client_id)
        authorization_endpoint = self.client.provider_info["authorization_endpoint"]
        self.client.storage.set(f"{state}_code_verifier", code_verifier)
        self.client.storage.set(f"{state}_redirect_url", get_callback_uri())

        params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "response_type": "code",
            "redirect_uri": get_callback_uri(),
            "client_id": self.client_id,
            # offline_access: also asks for refresh token
            "scope": "openid offline_access webid",
        }
        if extras_params is not None:
            params = {**params, **extras_params}
        return f"{authorization_endpoint}?{urllib.parse.urlencode(params)}"

    def authorize_button(
        self,
        name,
        height=800,
        width=600,
        key=None,
        extras_params={},
        icon=None,
        use_container_width=False,
    ):
        state = _generate_state(key)
        authorize_request_url = self.create_login_uri(state, extras_params)
        result = _authorize_button(
            authorization_url=authorize_request_url,
            name=name,
            popup_height=height,
            popup_width=width,
            key=key,
            icon=icon,
            use_container_width=use_container_width,
        )

        if result:
            if "error" in result:
                raise StreamlitOauthError(result)
            if "state" in result and result["state"] != state:
                raise StreamlitOauthError(
                    f"STATE {state} DOES NOT MATCH OR OUT OF DATE"
                )
            if "code" in result:
                token_endpoint = self.client.provider_info["token_endpoint"]
                key = jwcrypto.jwk.JWK.generate(kty="EC", crv="P-256")
                code_verifier = self.client.storage.get(f"{state}_code_verifier")

                res = requests.post(
                    token_endpoint,
                    auth=(
                        (self.client_id, self.client_secret)
                        if self.client_secret is not None
                        else None
                    ),
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.client_id,
                        "redirect_uri": get_callback_uri(),
                        "code": result["code"],
                        "code_verifier": code_verifier,
                    },
                    headers={
                        "DPoP": create_dpop_token(key, token_endpoint, "POST"),
                    },
                    allow_redirects=False,
                )

                assert res.ok, f"Could not get access token: {res.text}"
                access_token = res.json()["access_token"]
                self.client.storage.remove(f"{state}_code_verifier")
                result["token"] = SolidAuthSession(access_token, key).serialize()

        return result

    def refresh_token(self, token, force=False):
        """
        Returns a refreshed token if the token is expired, otherwise returns the same token
        """
        raise NotImplementedError("Solid OIDC Refresh token not implemented yet")
        # if force or token.get('expires_at') and token['expires_at'] < time.time():
        #   if token.get('refresh_token') is None:
        #     raise Exception("Token is expired and no refresh token is available")
        #   else:
        #     token = asyncio.run(self.client.refresh_token(token.get('refresh_token')))
        # return token

    def revoke_token(self, token, token_type_hint="access_token"):
        """
        Revokes the token
        """
        raise NotImplementedError("Solid OIDC Revoke token not implemented yet")
        # if token_type_hint == "access_token":
        #   token = token['access_token']
        # elif token_type_hint == "refresh_token":
        #   token = token['refresh_token']
        # try:
        #   asyncio.run(self.client.revoke_token(token, token_type_hint))
        # except:
        #   # discard exception if revoke fails
        #   pass
        # return True
