#include "MiruValidationProbe.h"
#include "MiruVehicleTools.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/SpectatorPawn.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/FileManager.h"
#include "WheeledVehicleMovementComponent4W.h"
#include "GameFramework/Pawn.h"
#include "Animation/AnimInstance.h"
#include "Engine/GameViewportClient.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/DateTime.h"
#include "Serialization/JsonSerializer.h"
#include "Components/SkeletalMeshComponent.h"

namespace {
FString Mode() {
    FString Value=TEXT("vehicle");
    FParse::Value(FCommandLine::Get(),TEXT("SimulatorMode="),Value);
    return Value;
}
FString OutputDirectory() {
    FString Value;
    if (!FParse::Value(FCommandLine::Get(),TEXT("SimulatorOutput="),Value))
        Value=FPaths::ProjectDir()/TEXT("local/latest");
    return FPaths::ConvertRelativePathToFull(Value);
}
}
ASimulatorMapGameMode::ASimulatorMapGameMode()
{
    DefaultPawnClass=ASpectatorPawn::StaticClass();
    HUDClass=nullptr;
}

void AMiruSimBootstrap::BeginPlay()
{
    Super::BeginPlay();
    if (Mode()==TEXT("map")) return;
    UClass* SimClass=LoadClass<AActor>(nullptr,TEXT("/Script/AirSim.SimModeCar"));
    if (!SimClass) { UE_LOG(LogTemp,Error,TEXT("MIRU: SimModeCar class missing")); return; }
    for (TActorIterator<AActor> It(GetWorld(),SimClass);It;++It) return;
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* Sim=GetWorld()->SpawnActor<AActor>(SimClass,FTransform::Identity,Params);
    UFunction* Start=Sim ? Sim->FindFunction(TEXT("startApiServer")) : nullptr;
    if (!Start) { UE_LOG(LogTemp,Error,TEXT("MIRU: startApiServer missing")); return; }
    Sim->ProcessEvent(Start,nullptr);
    UE_LOG(LogTemp,Display,TEXT("Simulator: common bootstrap started FSDS and RPC"));
}

AMiruValidationProbe::AMiruValidationProbe()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickInterval=.1f;
}
void AMiruValidationProbe::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    auto Report=MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("mode"),Mode());
    Report->SetNumberField(TEXT("time"),FDateTime::UtcNow().ToUnixTimestamp());
    Report->SetNumberField(TEXT("simulation_seconds"),GetWorld()->GetTimeSeconds());
    Report->SetStringField(TEXT("map"),GetWorld()->GetOutermost()->GetName());
    TArray<TSharedPtr<FJsonValue>> Vehicles;
    for (TActorIterator<APawn> It(GetWorld());It;++It) {
        auto* Car=*It;
        if (!Car->FindComponentByClass<UWheeledVehicleMovementComponent4W>()) continue;
        TSharedPtr<FJsonObject> R;
        if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(UMiruVehicleTools::DescribeVehicle(Car)),R)) continue;
        const auto Pos=Car->GetActorLocation(); const auto Rot=Car->GetActorRotation();
        R->SetStringField(TEXT("vehicle_name"),Car->GetName());
        R->SetNumberField(TEXT("x_cm"),Pos.X); R->SetNumberField(TEXT("y_cm"),Pos.Y); R->SetNumberField(TEXT("z_cm"),Pos.Z);
        R->SetNumberField(TEXT("roll_deg"),Rot.Roll); R->SetNumberField(TEXT("pitch_deg"),Rot.Pitch); R->SetNumberField(TEXT("yaw_deg"),Rot.Yaw);
        if (auto* Mesh=Car->FindComponentByClass<USkeletalMeshComponent>()) {
            R->SetNumberField(TEXT("world_com_z_cm"),Mesh->GetCenterOfMass().Z);
            R->SetStringField(TEXT("animation_class"),Mesh->GetAnimInstance() ? Mesh->GetAnimInstance()->GetClass()->GetPathName() : TEXT("none"));
        }
        Vehicles.Add(MakeShared<FJsonValueObject>(R));
    }
    Report->SetArrayField(TEXT("vehicles"),Vehicles);
    const FString Directory=OutputDirectory();
    IFileManager::Get().MakeDirectory(*Directory,true);
    FString Out; FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Out));
    const FString File=Directory/TEXT("physics.json");
    if (FFileHelper::SaveStringToFile(Out,*(File+TEXT(".tmp"))))
        IFileManager::Get().Move(*File,*(File+TEXT(".tmp")),true,true);
    if (!bScreenshotRequested && GetWorld()->GetTimeSeconds()>4) {
        FScreenshotRequest::RequestScreenshot(Directory/TEXT("preview.png"),false,false);
        bScreenshotRequested=true;
    }
}
