#!/bin/sh
set -eu

"$(dirname "$0")/verify-frontend.sh"
"$(dirname "$0")/verify-rust.sh"
