#!/bin/sh -e

python3 -m xipd test/test.xipd > test/new.pd
trap 'rm test/new.pd' EXIT
diff -u test/test.pd test/new.pd
echo 'all fine!'
