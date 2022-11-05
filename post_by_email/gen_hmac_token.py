#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys
import itsdangerous
import hashlib


def main(secret_key, email_addr):
    sep = "^"
    signer = itsdangerous.Signer(secret_key, sep=sep, digest_method=hashlib.sha256)

    print(signer.sign(email_addr).split(sep, 2)[1])


if __name__ == "__main__":
    main(*sys.argv[1:])
