#include "MiruVehicleTools.h"
#include "WheeledVehicleMovementComponent4W.h"
#include "VehicleWheel.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimBlueprint.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#if WITH_EDITOR
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Engine/LevelScriptBlueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "UObject/ObjectRedirector.h"
#endif

bool UMiruVehicleTools::ClearLevelScript(UWorld* World)
{
#if WITH_EDITOR
    if (!World || !World->PersistentLevel) return false;
    ULevelScriptBlueprint* BP=World->PersistentLevel->GetLevelScriptBlueprint(true);
    if (!BP) return true;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    for (auto* Graph : Graphs) {
        const auto Nodes=Graph->Nodes;
        for (auto* Node : Nodes) FBlueprintEditorUtils::RemoveNode(BP,Node,true);
    }
    FKismetEditorUtilities::CompileBlueprint(BP);
    BP->MarkPackageDirty(); World->MarkPackageDirty();
    return BP->Status!=BS_Error;
#else
    return false;
#endif
}

void UMiruVehicleTools::FixRedirectors(const TArray<UObject*>& Objects)
{
#if WITH_EDITOR
    TArray<UObjectRedirector*> Redirectors;
    for (auto* Object : Objects)
        if (auto* Redirector=Cast<UObjectRedirector>(Object)) Redirectors.Add(Redirector);
    FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get().FixupReferencers(Redirectors);
#endif
}

bool UMiruVehicleTools::ConfigureMotor(AActor* Vehicle, const FString& ProfileFile)
{
    if (!Vehicle) return false;
    auto* Move=Vehicle->FindComponentByClass<UWheeledVehicleMovementComponent4W>();
    FString Text; TSharedPtr<FJsonObject> P;
    if (!Move || !FFileHelper::LoadFileToString(Text,*ProfileFile) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),P)) return false;
    const float Torque=P->GetNumberField(TEXT("motor_peak_torque_nm"));
    const float Power=P->GetNumberField(TEXT("motor_peak_power_w"));
    const float Plateau=P->GetNumberField(TEXT("motor_constant_torque_end_rpm"));
    const float MaxRPM=P->GetNumberField(TEXT("simulation_motor_cutoff_rpm"));
    // EV approximation on PhysX Drive4W: no ICE damping, one forward ratio.
    // The curve beyond the donor's published torque plateau is inferred.
    auto& Engine=Move->EngineSetup;
    Engine.MaxRPM=MaxRPM; Engine.MOI=P->GetNumberField(TEXT("motor_moi_kg_m2"));
    Engine.DampingRateFullThrottle=0; Engine.DampingRateZeroThrottleClutchEngaged=0;
    Engine.DampingRateZeroThrottleClutchDisengaged=0;
    Engine.TorqueCurve.ExternalCurve=nullptr;
    auto* Curve=Engine.TorqueCurve.GetRichCurve(); Curve->Reset();
    // Piecewise linear values: peak torque through 2100, then conservative
    // 12.535 kW envelope, bounded below the published 13 kW peak.
    // PhysX accepts at most 8 points. MaxRPM is an explicit simulation limit.
    const float EffectivePower=FMath::Min(Power,Torque*Plateau*2*PI/60);
    const float Rpms[]={0,Plateau,3000,4200,5600,6800,MaxRPM-100,MaxRPM};
    for (int I=0; I<8; ++I) {
        float T=I==7 ? 0 : (Rpms[I]<=Plateau ? Torque : EffectivePower*60/(2*PI*Rpms[I]));
        auto H=Curve->AddKey(Rpms[I],T); Curve->SetKeyInterpMode(H,RCIM_Linear);
    }
    auto& G=Move->TransmissionSetup;
    G.bUseGearAutoBox=true; G.GearSwitchTime=0; G.GearAutoBoxLatency=0;
    G.FinalRatio=P->GetNumberField(TEXT("reduction_ratio"));
    G.ReverseGearRatio=-1; G.NeutralGearUpRatio=0; G.ClutchStrength=100;
    if (G.ForwardGears.Num()<1) return false;
    G.ForwardGears.RemoveAt(1,G.ForwardGears.Num()-1);
    auto& Gear=G.ForwardGears[0]; Gear.Ratio=1; Gear.DownRatio=0; Gear.UpRatio=1;
    Move->DifferentialSetup.DifferentialType=EVehicleDifferential4W::Open_RearDrive;
    Move->DifferentialSetup.FrontRearSplit=0;
    Move->DifferentialSetup.RearLeftRightSplit=0.5f;
    Move->SteeringCurve.ExternalCurve=nullptr;
    auto* Steering=Move->SteeringCurve.GetRichCurve(); Steering->Reset();
    Steering->AddKey(0,1); Steering->AddKey(200,1);
    Move->MarkPackageDirty(); Vehicle->MarkPackageDirty();
    return true;
}

bool UMiruVehicleTools::RetargetWheelAnimation(UObject* AnimationBlueprint, USkeletalMesh* Mesh)
{
#if WITH_EDITOR
    auto* BP=Cast<UAnimBlueprint>(AnimationBlueprint);
    if (!BP || !Mesh) return false;
    BP->TargetSkeleton=Mesh->Skeleton;
    FKismetEditorUtilities::CompileBlueprint(BP);
    BP->MarkPackageDirty();
    return BP->Status!=BS_Error;
#else
    return false;
#endif
}

FString UMiruVehicleTools::DescribeVehicle(AActor* Vehicle)
{
    if (!Vehicle) return TEXT("{}");
    auto* M=Vehicle->FindComponentByClass<UWheeledVehicleMovementComponent4W>();
    auto* S=Vehicle->FindComponentByClass<USkeletalMeshComponent>();
    if (!M || !S || !S->SkeletalMesh) return TEXT("{}");
    auto R=MakeShared<FJsonObject>();
    R->SetStringField(TEXT("class"),Vehicle->GetClass()->GetPathName());
    R->SetStringField(TEXT("mesh"),S->SkeletalMesh ? S->SkeletalMesh->GetPathName() : TEXT(""));
    R->SetNumberField(TEXT("mass_kg"),M->Mass);
    R->SetNumberField(TEXT("runtime_physics_mass_kg"),S->GetMass());
    R->SetNumberField(TEXT("differential_type"),int(M->DifferentialSetup.DifferentialType));
    R->SetNumberField(TEXT("final_ratio"),M->TransmissionSetup.FinalRatio);
    R->SetNumberField(TEXT("max_rpm"),M->EngineSetup.MaxRPM);
    R->SetNumberField(TEXT("full_throttle_damping"),M->EngineSetup.DampingRateFullThrottle);
    R->SetNumberField(TEXT("coast_damping"),M->EngineSetup.DampingRateZeroThrottleClutchEngaged);
    R->SetNumberField(TEXT("rpm"),M->GetEngineRotationSpeed());
    R->SetNumberField(TEXT("gear"),M->GetCurrentGear());
    R->SetNumberField(TEXT("speed_mps"),M->GetForwardSpeed()/100);
    TArray<TSharedPtr<FJsonValue>> Points, Gears, Wheels;
    for (const auto& K:M->EngineSetup.TorqueCurve.GetRichCurveConst()->GetConstRefOfKeys()) {
        auto V=MakeShared<FJsonObject>(); V->SetNumberField(TEXT("rpm"),K.Time);V->SetNumberField(TEXT("torque_nm"),K.Value);
        Points.Add(MakeShared<FJsonValueObject>(V));
    }
    for (const auto& G:M->TransmissionSetup.ForwardGears) Gears.Add(MakeShared<FJsonValueNumber>(G.Ratio));
    for (int I=0;I<M->WheelSetups.Num();++I) {
        auto& Setup=M->WheelSetups[I];
        if (!Setup.WheelClass) return TEXT("{}");
        auto* W=Setup.WheelClass->GetDefaultObject<UVehicleWheel>();
        auto V=MakeShared<FJsonObject>(); V->SetStringField(TEXT("bone"),Setup.BoneName.ToString());
        const int Bone=S->GetBoneIndex(Setup.BoneName);
        FVector Pos=Bone>=0 ? S->SkeletalMesh->GetRefSkeleton().GetRefBonePose()[Bone].GetLocation() : FVector::ZeroVector;
        Pos+=Setup.AdditionalOffset+W->Offset;
        V->SetNumberField(TEXT("x_cm"),Pos.X);V->SetNumberField(TEXT("y_cm"),Pos.Y);V->SetNumberField(TEXT("z_cm"),Pos.Z);
        V->SetNumberField(TEXT("radius_cm"),W->ShapeRadius);V->SetNumberField(TEXT("width_cm"),W->ShapeWidth);
        V->SetNumberField(TEXT("steer_limit_deg"),W->SteerAngle);
        if (M->Wheels.IsValidIndex(I)) { auto* Live=M->Wheels[I];
            V->SetNumberField(TEXT("steer_deg"),Live->GetSteerAngle());
            V->SetNumberField(TEXT("rotation_deg"),Live->GetRotationAngle());
            V->SetNumberField(TEXT("suspension_offset_cm"),Live->GetSuspensionOffset());
            V->SetBoolField(TEXT("in_air"),Live->IsInAir());
            const UPhysicalMaterial* Surface=Live->GetContactSurfaceMaterial();
            V->SetStringField(TEXT("contact_material"),Surface ? Surface->GetPathName() : TEXT("none"));
            if (Surface) V->SetNumberField(TEXT("contact_material_friction"),Surface->Friction);
        }
        Wheels.Add(MakeShared<FJsonValueObject>(V));
    }
    R->SetArrayField(TEXT("torque_curve"),Points); R->SetArrayField(TEXT("forward_ratios"),Gears);R->SetArrayField(TEXT("wheels"),Wheels);
    FString Out; FJsonSerializer::Serialize(R,TJsonWriterFactory<>::Create(&Out)); return Out;
}
