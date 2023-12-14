# common.py
#
# ALGORITHM_CHOICES are options for alg attribute in DS data
# reference:
# https://www.iana.org/assignments/dns-sec-alg-numbers/dns-sec-alg-numbers.xhtml
ALGORITHM_CHOICES = [
    (1, "(1) ERSA/MD5 [RSAMD5]"),
    (2, "(2) Diffie-Hellman [DH]"),
    (3, "(3) DSA/SHA-1 [DSA]"),
    (5, "(5) RSA/SHA-1 [RSASHA1]"),
    (6, "(6) DSA-NSEC3-SHA1"),
    (7, "(7) RSASHA1-NSEC3-SHA1"),
    (8, "(8) RSA/SHA-256 [RSASHA256]"),
    (10, "(10) RSA/SHA-512 [RSASHA512]"),
    (12, "(12) GOST R 34.10-2001 [ECC-GOST]"),
    (13, "(13) ECDSA Curve P-256 with SHA-256 [ECDSAP256SHA256]"),
    (14, "(14) ECDSA Curve P-384 with SHA-384 [ECDSAP384SHA384]"),
    (15, "(15) Ed25519"),
    (16, "(16) Ed448"),
]
# DIGEST_TYPE_CHOICES are options for digestType attribute in DS data
# reference: https://datatracker.ietf.org/doc/html/rfc4034#appendix-A.2
DIGEST_TYPE_CHOICES = [
    (1, "(1) SHA-1"),
    (2, "(2) SHA-256"),
]
