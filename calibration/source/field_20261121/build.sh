#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
FOLLOWUP_ENGINE="${SIMULATOR_ENGINE_ROOT:-/home/simseunghwan/UnrealEngine}"
export UE_MONO_DIR="$FOLLOWUP_ENGINE/Engine/Binaries/ThirdParty/Mono/Linux"
exec "$UE_MONO_DIR/bin/mono" "$FOLLOWUP_ENGINE/Engine/Binaries/DotNET/UnrealBuildTool.exe" \
  BlocksEditor Linux Development "-Project=$PWD/simulator/variants/field_20261121/FSOnline.uproject" \
  -Module=AirSim -Module=Blocks -UsePrecompiled -NoEngineChanges -NoHotReloadFromIDE \
  "-Log=$PWD/experiments/evidence/2026-11-21_field_followup/build.log"
