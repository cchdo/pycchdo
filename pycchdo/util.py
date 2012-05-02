def flatten(l):
    return [item for sublist in l for item in sublist]


def str2uni(x):
    if type(x) is str:
        return unicode(x)
    return x


def is_valid_ipv4(ip):
    try:
        return socket.inet_pton(socket.AF_INET, ip)
    except AttributeError: # no inet_pton here, sorry
        try:
            return socket.inet_aton(ip)
        except socket.error:
            return False
    except socket.error:
        return False


def is_valid_ipv6(ip):
    try:
        return socket.inet_pton(socket.AF_INET6, ip)
    except socket.error:
        return False


def is_valid_ip(ip):
    return is_valid_ipv4(ip) or is_valid_ipv6(ip)
