# common.py
# reference: https://www.iana.org/assignments/dns-sec-alg-numbers/dns-sec-alg-numbers.xhtml
ALGORITHM_CHOICES = [
    (1, "ERSA/MD5 [RSAMD5]"),
    (2 , "Diffie-Hellman [DH]"),
    (3 ,"DSA/SHA-1 [DSA]"),
    (5 ,"RSA/SHA-1 [RSASHA1]"),
    (6 ,"DSA-NSEC3-SHA1"),
    (7 ,"RSASHA1-NSEC3-SHA1"),
    (8 ,"RSA/SHA-256 [RSASHA256]"),
    (10 ,"RSA/SHA-512 [RSASHA512]"),
    (12 ,"GOST R 34.10-2001 [ECC-GOST]"),
    (13 ,"ECDSA Curve P-256 with SHA-256 [ECDSAP256SHA256]"),
    (14 ,"ECDSA Curve P-384 with SHA-384 [ECDSAP384SHA384]"),
    (15 ,"Ed25519"),
    (16 ,"Ed448"),
]
# Q: What are the options?
DIGEST_TYPE_CHOICES = [
    (0, "Reserved"),
    (1, "SHA-256"),
]
# Flag choices
FLAG_CHOICES = [
    (0, "0"),
    (256, "256"),
    (257, "257"),
]
