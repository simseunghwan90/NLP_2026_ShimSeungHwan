#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
CREEP_ENGINE="${SIMULATOR_ENGINE_ROOT:-/home/simseunghwan/UnrealEngine}"
export UE_MONO_DIR="$CREEP_ENGINE/Engine/Binaries/ThirdParty/Mono/Linux"
exec "$UE_MONO_DIR/bin/mono" "$CREEP_ENGINE/Engine/Binaries/DotNET/UnrealBuildTool.exe" \
  BlocksEditor Linux Development "-Project=$PWD/simulator/variants/r5_creep_viscous_20261122/FSOnline.uproject" \
  -Module=AirSim -Module=Blocks -UsePrecompiled -NoEngineChanges -NoHotReloadFromIDE -MaxParallelActions=2 \
  "-Log=$PWD/experiments/evidence/2026-11-22_r5_stages/build_creep_viscous.log"
