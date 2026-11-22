#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/GameModeBase.h"
#include "MiruValidationProbe.generated.h"

/** Read-only telemetry in the dedicated test map. Never actuates the car. */
UCLASS()
class BLOCKS_API AMiruValidationProbe : public AActor
{
    GENERATED_BODY()
public:
    AMiruValidationProbe();
    virtual void Tick(float DeltaSeconds) override;
private:
    bool bScreenshotRequested=false;
};

/** Start FSDS in the isolated test map without the cooked-only bootstrap BP. */
UCLASS()
class BLOCKS_API AMiruSimBootstrap : public AActor
{
    GENERATED_BODY()
public:
    virtual void BeginPlay() override;
};

/** A map viewer has no AirSim HUD, vehicles, or RPC server. */
UCLASS()
class BLOCKS_API ASimulatorMapGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ASimulatorMapGameMode();
};
