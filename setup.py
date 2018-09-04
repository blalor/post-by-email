#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="post_by_email",
    version="0.0.1",
    author="Brian Lalor",
    author_email="blalor@bravo5.org",
    description="post to a jekyll blog via email, with photo support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/blalor/post-by-email",

    packages=find_packages(),
    install_requires=[
        "dulwich==0.18.6", #  --global-option=--pure
        "boto3 >=1.7,<2",
        "itsdangerous >=0.24,<1",
        "rtyaml",

        "ExifRead >=2.1,<3",
        "python-slugify >=1.2,<2",
        "geopy >=1.16,<2",
    ],
    tests_require=[
        "nose",
        "mock",
    ],
    test_suite="nose.collector",
)
