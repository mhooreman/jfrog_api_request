# jfrog_api_request

Provides the `jfrog-api-request` command line tool.

It runs an jfrog API query, and print the result as an evaluable python
code or, if not possible, a text representation of the output.

This script uses PIP configuration for JFrog, but is intended to be used
for debugging while JFrog has problems.

So it means that we can't rely on JFrog, and ONLY vanilla python can be used.
So:
- we use curl as backend
- no additional dependencies are allowed (except development dependencies)
