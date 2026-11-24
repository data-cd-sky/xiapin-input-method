#!/usr/bin/env bash
# Execute commands inside the project's dedicated Ubuntu test VMs through the
# QEMU guest agent. This script is intentionally outside the package build.
set -Eeuo pipefail

usage() {
    echo "usage: $0 [22|24|26] <shell command>" >&2
    echo "       $0 put [22|24|26] <host file> <guest path>" >&2
    echo "       $0 get [22|24|26] <guest path> <host file>" >&2
    exit 2
}

operation=run
if [[ ${1:-} == put || ${1:-} == get ]]; then
    operation=$1
    shift
    [[ $# -eq 3 ]] || usage
else
    [[ $# -eq 2 ]] || usage
fi
version=$1
if [[ $operation == run ]]; then
    command_text=$2
else
    transfer_source=$2
    transfer_destination=$3
fi

case "$version" in
    22|24|26) ;;
    *) usage ;;
esac

vm="xiapin-ubuntu-$version"
libvirt_uri="qemu:///session"

json_escape() {
    python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

agent() {
    virsh -c "$libvirt_uri" qemu-agent-command "$vm" "$1"
}

put_file() {
    local handle offset size
    handle=$(agent "{\"execute\":\"guest-file-open\",\"arguments\":{\"path\":$(json_escape "$2"),\"mode\":\"wb\"}}" |
        python3 -c 'import json,sys; print(json.load(sys.stdin)["return"])')
    offset=0
    while IFS= read -r chunk; do
        agent "{\"execute\":\"guest-file-write\",\"arguments\":{\"handle\":$handle,\"buf-b64\":\"$chunk\"}}" \
            >/dev/null
        offset=$((offset + $(printf '%s' "$chunk" | base64 -d | wc -c)))
    done < <(base64 -w 6144 "$1")
    size=$(stat -c '%s' "$1")
    agent "{\"execute\":\"guest-file-close\",\"arguments\":{\"handle\":$handle}}" >/dev/null
    printf 'uploaded %s bytes to %s\n' "$size" "$2"
}

get_file() {
    local handle encoded source=$1 destination=$2
    handle=$(agent "{\"execute\":\"guest-file-open\",\"arguments\":{\"path\":$(json_escape "$source"),\"mode\":\"rb\"}}" |
        python3 -c 'import json,sys; print(json.load(sys.stdin)["return"])')
    : >"$destination"
    while true; do
        encoded=$(agent "{\"execute\":\"guest-file-read\",\"arguments\":{\"handle\":$handle,\"count\":1048576}}" |
            python3 -c 'import json,sys; print(json.load(sys.stdin)["return"].get("buf-b64",""))')
        [[ -n $encoded ]] || break
        printf '%s' "$encoded" | base64 -d >>"$destination"
    done
    agent "{\"execute\":\"guest-file-close\",\"arguments\":{\"handle\":$handle}}" >/dev/null
    printf 'downloaded %s bytes to %s\n' "$(stat -c '%s' "$destination")" "$destination"
}

run_guest() {
    local command_json pid status
    command_json=$(json_escape "$command_text")
    pid=$(agent "{\"execute\":\"guest-exec\",\"arguments\":{\"path\":\"/bin/sh\",\"arg\":[\"-c\",$command_json],\"capture-output\":true}}" |
        python3 -c 'import json,sys; print(json.load(sys.stdin)["return"]["pid"])')
    for _ in $(seq 1 600); do
        status=$(agent "{\"execute\":\"guest-exec-status\",\"arguments\":{\"pid\":$pid}}")
        if python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin)["return"].get("exited") else 1)' \
            <<<"$status"; then
            break
        fi
        sleep 0.5
    done
    python3 -c '
import base64
import json
import sys

result = json.load(sys.stdin)["return"]
if not result.get("exited"):
    raise SystemExit("guest command did not finish")
for key in ("out-data", "err-data"):
    data = result.get(key)
    if data:
        sys.stdout.buffer.write(base64.b64decode(data))
        sys.stdout.buffer.flush()
raise SystemExit(result.get("exitcode", 1))
' <<<"$status"
}

case "$operation" in
    run) run_guest ;;
    put) put_file "$transfer_source" "$transfer_destination" ;;
    get) get_file "$transfer_source" "$transfer_destination" ;;
esac
