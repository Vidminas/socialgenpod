import subprocess


def attessPossession(authorizationHeader, dpopHeader, requestMethod, requestURL, claimedWebid):
    '''
    To attest the user is actually the user it claims to be
    Or, maybe, at least, to attest that the user holds valid credentials -- being *a* valid Solid user
    '''
    args = [authorizationHeader, dpopHeader, requestMethod, requestURL]
    if claimedWebid:
        args.append(claimedWebid)
    ret = subprocess.call(('node', 'attest.js', *args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return not ret
