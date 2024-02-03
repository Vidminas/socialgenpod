import subprocess


def attessPossession(authorizationHeader, dpopHeader, requestMethod, requestURL, claimedWebid):
    '''
    To attest the actual WebID associated with the auth information.
    Can be used to attest the user is actually the user it claims to be (`claimedWebid`).
    Or, to attest that the user holds valid credentials -- being some valid Solid user.
    '''
    args = [authorizationHeader, dpopHeader, requestMethod, requestURL]
    if claimedWebid:
        args.append(claimedWebid)
    ret = subprocess.call(('node', 'attest.js', *args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return not ret
