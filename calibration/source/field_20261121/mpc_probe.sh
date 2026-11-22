#!/usr/bin/env bash
# 기존 MPC/BSW를 전용 network namespace에서 후보 차량에 연결한다.
set -euo pipefail
cd "$(dirname "$0")/../.."
export RESEARCH_PARENT_NETNS=$(readlink /proc/self/ns/net)
export RESEARCH_BSW_SOURCE_FILE="$PWD/experiments/bsw_main_source.json"
exec unshare -Ucn --keep-caps bash -c '
  set -euo pipefail
  cd "$1"; shift
  ip link set lo up
  ip link add vcan79 type vcan
  ip link set vcan79 up
  source scripts/env.sh
  source ros_ws/install_mpc_field/local_setup.bash
  exec python3 analysis/field_20261121/mpc_probe.py "$@"
' bash "$PWD" "$@"
