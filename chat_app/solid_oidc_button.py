import urllib.parse
import base64

import streamlit as st
from solid_oidc_client import SolidOidcClient, MemStore
from solid_oidc_client.solid_oidc_client import create_verifier_challenge
from streamlit_oauth import (
    OAuth2Component,
    StreamlitOauthError,
    _generate_state,
    _authorize_button,
)


@st.cache_data(ttl=300)
def generate_pkce_pair(client_id):
    return create_verifier_challenge()


class SolidOidcComponent(OAuth2Component):
    def __init__(self, solid_server_url: str, valid_redirect_uris: list[str]):
        client = SolidOidcClient(storage=MemStore())
        client.register_client(solid_server_url, valid_redirect_uris)
        super().__init__(
            client_id=None,
            client_secret=None,
            authorize_endpoint=None,
            token_endpoint=None,
            refresh_token_endpoint=None,
            revoke_token_endpoint=None,
            client=client,
        )

    def create_login_uri(self, state, redirect_uri, extras_params):
        code_verifier, code_challenge = generate_pkce_pair(self.client.client_id)
        authorization_endpoint = self.client.provider_info["authorization_endpoint"]
        self.client.storage.set(f"{state}_code_verifier", code_verifier)
        self.client.storage.set(f"{state}_redirect_url", redirect_uri)

        params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "client_id": self.client.client_id,
            # offline_access: also asks for refresh token
            "scope": "openid offline_access",
        }
        if extras_params is not None:
            params = {**params, **extras_params}

        return f"{authorization_endpoint}?{urllib.parse.urlencode(params)}"

    def authorize_button(
        self,
        name,
        redirect_uri,
        height=800,
        width=600,
        key=None,
        extras_params={},
        icon=None,
        use_container_width=False,
    ):
        state = _generate_state(key)
        authorize_request = self.create_login_uri(state, redirect_uri, extras_params)
        result = _authorize_button(
            authorization_url=authorize_request,
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
                session = self.client.finish_login(
                    result["code"], result["state"], redirect_uri
                )
                result["token"] = session.serialize()
            if "id_token" in result:
                # TODO: verify id_token
                result["id_token"] = base64.b64decode(
                    result["id_token"].split(".")[1] + "=="
                )

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
