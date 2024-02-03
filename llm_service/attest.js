const createSolidTokenVerifier =
  require("@solid/access-token-verifier").createSolidTokenVerifier;

/**
 * Check whether the request belongs to a / the corresponding WebID.
 * @param {string} authorizationHeader The `authorization` header
 * @param {string} dpopHeader The `DPoP` header
 * @param {string} requestMethod The HTTP method for the request
 * @param {string} requestURL The URL of the request
 * @param {string|undefined} claimedWebid What WebID the client claims to be (can be `undefined`)
 * @returns {boolean|string} If `claimedWebid` is not empty, return whether the claimed WebID matches the real WebID in the credentials; otherwise, return the real WebID.
 */
async function attestWebidPossession(
  authorizationHeader,
  dpopHeader,
  requestMethod,
  requestURL,
  claimedWebid
) {
  const solidOidcAccessTokenVerifier = createSolidTokenVerifier();

  try {
    const { client_id: clientId, webid: webId } =
      await solidOidcAccessTokenVerifier(authorizationHeader, {
        header: dpopHeader,
        method: requestMethod,
        url: requestURL,
      });

    if (!claimedWebid) {
      return webId;
    }

    return webId == claimedWebid;
  } catch (error) {
    const message = `Error verifying Access Token via WebID: ${error.message}`;
    throw new Error(message);
  }
}

// module.exports = {
//     attestWebidPossession,
// };

async function main() {
  const res = await attestWebidPossession(...process.argv.slice(2));

  if (res) {
    process.exit(0);
  } else {
    process.exit(1);
  }
}

main();
