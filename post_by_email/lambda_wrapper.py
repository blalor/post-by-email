#!/usr/bin/env python
# -*- encoding: utf-8 -*-

## this is because
## > module initialization error: Parent module 'post_by_email' not loaded, cannot perform relative import
## I don't understand how lambda does module loading…

from post_by_email import lambda_function

handler = lambda_function.lambda_handler
