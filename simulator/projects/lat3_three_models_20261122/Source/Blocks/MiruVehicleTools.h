#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "MiruVehicleTools.generated.h"

/** Authoring functions for the isolated, provisional MIRU EV profile. */
UCLASS()
class BLOCKS_API UMiruVehicleTools : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="MIRU")
    static bool ConfigureMotor(AActor* Vehicle, const FString& ProfileFile);
    UFUNCTION(BlueprintCallable, Category="MIRU")
    static bool RetargetWheelAnimation(UObject* AnimationBlueprint, USkeletalMesh* Mesh);
    UFUNCTION(BlueprintCallable, Category="MIRU")
    static FString DescribeVehicle(AActor* Vehicle);
    UFUNCTION(BlueprintCallable, Category="Simulator")
    static bool ClearLevelScript(UWorld* World);
    UFUNCTION(BlueprintCallable, Category="Simulator")
    static void FixRedirectors(const TArray<UObject*>& Objects);
};
