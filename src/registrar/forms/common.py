# common.py
# Q: What are the options?
ALGORITHM_CHOICES = [
    (1, "ERSA/MD5 [RSAMD5]"),
    (2 , "Diffie-Hellman [DH]"),
    (3 ,"DSA/SHA-1 [DSA]"),
    (5 ,"RSA/SHA-1 [RSASHA1]"),
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
