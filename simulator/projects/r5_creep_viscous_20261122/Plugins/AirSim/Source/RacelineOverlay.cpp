#include "WorldSimApi.h"
#include "AirBlueprintLib.h"
#include "Vehicles/Car/CarPawnSimApi.h"
#include "Components/LineBatchComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"
#include "TimerManager.h"

std::string WorldSimApi::simSetRaceline(const std::string& vehicle_name, const std::string& reference_id,
                                      const std::vector<Vector3r>& points)
{
    // Validate off the game thread so malformed RPC input cannot touch the scene.
    if (points.size() < 4 || points.size() > 100000 || reference_id.empty() || reference_id.size() > 128)
        throw std::invalid_argument("Invalid raceline size or reference id");
    for (const auto& p : points)
        if (!p.allFinite() || p.cwiseAbs().maxCoeff() > 1000000.f)
            throw std::invalid_argument("Nonfinite or out-of-range raceline point");
    if ((points.front()-points.back()).norm() > .001f)
        throw std::invalid_argument("Raceline must contain its closing endpoint");

    auto report = MakeShared<FJsonObject>();
    report->SetBoolField(TEXT("success"), false);
    report->SetStringField(TEXT("reference_id"), UTF8_TO_TCHAR(reference_id.c_str()));
    report->SetNumberField(TEXT("point_count"), points.size());
    UAirBlueprintLib::RunCommandOnGameThread([&]() {
        UWorld* world = simmode_->GetWorld();
        report->SetStringField(TEXT("map"), world->GetOutermost()->GetName());
        auto* vehicle = simmode_->getVehicleSimApi(vehicle_name);
        if (!vehicle) {
            report->SetStringField(TEXT("error"), TEXT("Unknown vehicle"));
            return;
        }
        const auto& transform = vehicle->getNedTransform();
        FCollisionQueryParams query(SCENE_QUERY_STAT(RacelineGround), true);
        TArray<AActor*> oldLines;
        UGameplayStatics::GetAllActorsWithTag(world, TEXT("YonginRacelineVisualization"), oldLines);
        TArray<AActor*> selected;
        UGameplayStatics::GetAllActorsWithTag(world, TEXT("SelectedRacelineVisualization"), selected);
        for (auto* actor : oldLines) query.AddIgnoredActor(actor);
        for (auto* actor : selected) query.AddIgnoredActor(actor);
        for (TActorIterator<APawn> it(world); it; ++it) query.AddIgnoredActor(*it);
        FCollisionObjectQueryParams objects;
        objects.AddObjectTypesToQuery(ECC_WorldStatic);

        TArray<FVector> ground;
        ground.Reserve(points.size());
        float minZ = TNumericLimits<float>::Max(), maxZ = TNumericLimits<float>::Lowest();
        for (size_t i = 0; i < points.size(); ++i) {
            const FVector p = transform.fromLocalEnu(points[i]);
            FHitResult hit;
            // Single road layer: never use a made-up flat height on a miss.
            if (!world->LineTraceSingleByObjectType(hit, p+FVector(0,0,100000), p-FVector(0,0,100000), objects, query)
                || hit.ImpactNormal.Z < .5f) {
                report->SetStringField(TEXT("error"), TEXT("No usable static ground under reference"));
                report->SetNumberField(TEXT("failed_point"), i);
                return;
            }
            ground.Add(hit.ImpactPoint+FVector(0,0,3));
            minZ = FMath::Min(minZ, hit.ImpactPoint.Z);
            maxZ = FMath::Max(maxZ, hit.ImpactPoint.Z);
        }
        // Only commit after every point projects. Preserve the previous display
        // on failure, and never flush other tools' persistent debug markers.
        AActor* overlay = selected.Num() ? selected[0] : nullptr;
        if (!overlay) {
            FActorSpawnParameters params;
            params.ObjectFlags |= RF_Transient;
            overlay = world->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, params);
            if (!overlay) {
                report->SetStringField(TEXT("error"), TEXT("Cannot create raceline overlay"));
                return;
            }
            overlay->Tags.Add(TEXT("SelectedRacelineVisualization"));
            auto* component = NewObject<ULineBatchComponent>(overlay, NAME_None, RF_Transient);
            overlay->AddInstanceComponent(component);
            overlay->SetRootComponent(component);
            component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            component->bCalculateAccurateBounds = true;
            component->RegisterComponent();
        }
        auto* lines = overlay->FindComponentByClass<ULineBatchComponent>();
        if (!lines) {
            report->SetStringField(TEXT("error"), TEXT("Invalid raceline overlay component"));
            return;
        }
        TArray<FBatchedLine> segments;
        segments.Reserve(ground.Num()-1);
        for (int32 i=1; i<ground.Num(); ++i)
            segments.Emplace(ground[i-1], ground[i], FLinearColor::Yellow, -1.f, 5.f, SDPG_World);
        lines->Flush();
        lines->DrawLines(segments);
        overlay->SetActorHiddenInGame(false);
        for (auto* actor : oldLines) actor->SetActorHiddenInGame(true);
        for (int32 i=1; i<selected.Num(); ++i) selected[i]->Destroy();

        const bool hideSensors = !FParse::Param(FCommandLine::Get(), TEXT("SensorRacelineVisible"));
        int32 captures = 0;
        if (hideSensors) {
            for (TActorIterator<AActor> it(world); it; ++it) {
                TArray<USceneCaptureComponent2D*> components;
                it->GetComponents(components);
                for (auto* capture : components) {
                    capture->HiddenActors.AddUnique(overlay);
                    ++captures;
                }
            }
        }
        auto vectorJson = [](const FVector& p) {
            TArray<TSharedPtr<FJsonValue>> result;
            for (float value : {p.X,p.Y,p.Z}) result.Add(MakeShared<FJsonValueNumber>(value));
            return result;
        };
        report->SetBoolField(TEXT("success"), true);
        report->SetStringField(TEXT("actor"), overlay->GetName());
        report->SetStringField(TEXT("coordinate_frame"), TEXT("vehicle getCarState local ENU metres"));
        report->SetArrayField(TEXT("vehicle_origin_cm"), vectorJson(transform.getLocalOffset()));
        report->SetArrayField(TEXT("global_origin_cm"), vectorJson(transform.getGlobalOffset()));
        report->SetArrayField(TEXT("first_world_cm"), vectorJson(ground[0]));
        report->SetNumberField(TEXT("ground_min_z_cm"), minZ);
        report->SetNumberField(TEXT("ground_max_z_cm"), maxZ);
        report->SetNumberField(TEXT("height_offset_cm"), 3);
        report->SetNumberField(TEXT("hidden_static_lines"), oldLines.Num());
        report->SetBoolField(TEXT("hidden_in_sensors"), hideSensors);
        report->SetNumberField(TEXT("sensor_capture_count"), captures);
        report->SetNumberField(TEXT("active_overlay_count"), 1);

        // Optional rendered evidence for validation; absent in normal launches.
        FString proofDirectory;
        if (FParse::Value(FCommandLine::Get(), TEXT("RacelineProofDirectory="), proofDirectory)) {
            const FString proof = proofDirectory / (FString::Printf(TEXT("raceline_%llu.png"),
                static_cast<unsigned long long>(FPlatformTime::Cycles64())));
            FTimerHandle timer;
            world->GetTimerManager().SetTimer(timer, [proof]() {
                FScreenshotRequest::RequestScreenshot(proof, false, false);
            }, .5f, false);
            report->SetStringField(TEXT("screenshot"), proof);
        }
    }, true);
    FString serialized;
    FJsonSerializer::Serialize(report, TJsonWriterFactory<>::Create(&serialized));
    return TCHAR_TO_UTF8(*serialized);
}
