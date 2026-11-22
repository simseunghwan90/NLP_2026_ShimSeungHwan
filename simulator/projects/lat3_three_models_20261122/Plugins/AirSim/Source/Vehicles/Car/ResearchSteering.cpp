#include "ResearchSteering.h"
#include "WheeledVehicleMovementComponent4W.h"
#include "VehicleWheel.h"
#include "PhysXVehicleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"
#include <iomanip>

ResearchSteering::ResearchSteering(UWheeledVehicleMovementComponent* movement) : movement_(movement)
{
    FString path, text;
    if (!FParse::Value(FCommandLine::Get(), TEXT("ResearchSteering="), path)) return;
    if (!FFileHelper::LoadFileToString(text, *path) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(text), config_))
        throw std::runtime_error("Invalid ResearchSteering JSON");
    state_.delay = config_->GetNumberField(TEXT("effective_delay_s"));
    config_->TryGetBoolField(TEXT("baseline_passthrough"), passthrough_);
    state_.omega = config_->GetNumberField(TEXT("natural_frequency_rad_s"));
    state_.zeta = config_->GetNumberField(TEXT("damping_ratio"));
    state_.rate_limit = config_->GetNumberField(TEXT("estimated_rate_limit_deg_s"));
    state_.limit = config_->GetNumberField(TEXT("handwheel_limit_deg"));
    ratio_ = config_->GetNumberField(TEXT("handwheel_to_nominal_tire_ratio"));
    geometry_.ratio = ratio_;
    if (config_->HasField(TEXT("handwheel_to_inner_tire_deg"))) {
        for (const auto& point : config_->GetArrayField(TEXT("handwheel_to_inner_tire_deg"))) {
            const auto& p = point->AsArray();
            if (p.Num() != 2) throw std::runtime_error("Invalid geometry pair");
            geometry_.points.emplace_back(p[0]->AsNumber(), p[1]->AsNumber());
        }
    }
    geometry_.validate(state_.limit);
    resolution_ = config_->GetNumberField(TEXT("handwheel_resolution_deg"));
    state_.validate();
    if (!std::isfinite(ratio_) || ratio_ <= 0 || !std::isfinite(resolution_) || resolution_ <= 0)
        throw std::runtime_error("Invalid steering ratio/resolution");
    telemetry_.open(TCHAR_TO_UTF8(*config_->GetStringField(TEXT("telemetry_path"))));
    if (!telemetry_) throw std::runtime_error("Cannot open steering telemetry");
    telemetry_ << std::setprecision(12)
        << "simulation_s,dt_s,can_target_handwheel_deg,model_handwheel_deg,model_rate_deg_s,fl_tire_deg,fr_tire_deg,actual_handwheel_deg\n";
}

void ResearchSteering::configure()
{
    if (!movement_->PVehicle || movement_->Wheels.Num() != 4) return;
    for (int i=0; !passthrough_ && i<2; ++i) {
        auto wheel = movement_->PVehicle->mWheelsSimData.getWheelData(i);
        wheel.mMaxSteer = FMath::DegreesToRadians(geometry_.tire_limit(state_.limit));
        movement_->PVehicle->mWheelsSimData.setWheelData(i, wheel);
        movement_->Wheels[i]->SteerAngle = geometry_.tire_limit(state_.limit);
    }
    // Replace only legacy steering slew/smoothing with this physical model.
    // Both UE and PhysX use these values; throttle/brake rates are untouched.
    auto* rate_property = FindFProperty<FStructProperty>(movement_->GetClass(), TEXT("SteeringInputRate"));
    if (!rate_property) throw std::runtime_error("SteeringInputRate property missing");
    auto* rate = rate_property->ContainerPtrToValuePtr<FVehicleInputRate>(movement_);
    const float original_rise = rate->RiseRate, original_fall = rate->FallRate;
    if (!passthrough_) {
        rate->RiseRate = 100000.f;
        rate->FallRate = 100000.f;
    }
    auto resolved = MakeShared<FJsonObject>();
    resolved->SetStringField(TEXT("model_sha256"), config_->GetStringField(TEXT("model_sha256")));
    resolved->SetStringField(TEXT("model_id"), config_->GetStringField(TEXT("model_id")));
    resolved->SetBoolField(TEXT("baseline_passthrough"), passthrough_);
    resolved->SetNumberField(TEXT("handwheel_limit_deg"), state_.limit);
    resolved->SetNumberField(TEXT("nominal_tire_limit_deg"), geometry_.tire_limit(state_.limit));
    if (config_->HasField(TEXT("handwheel_to_inner_tire_deg")))
        resolved->SetArrayField(TEXT("handwheel_to_inner_tire_deg"), config_->GetArrayField(TEXT("handwheel_to_inner_tire_deg")));
    resolved->SetNumberField(TEXT("handwheel_to_nominal_tire_ratio"), ratio_);
    resolved->SetNumberField(TEXT("effective_delay_s"), state_.delay);
    resolved->SetNumberField(TEXT("estimated_rate_limit_deg_s"), state_.rate_limit);
    resolved->SetNumberField(TEXT("natural_frequency_rad_s"), state_.omega);
    resolved->SetNumberField(TEXT("damping_ratio"), state_.zeta);
    resolved->SetNumberField(TEXT("legacy_steering_smoothing_rate"), rate->RiseRate);
    resolved->SetNumberField(TEXT("original_steering_rise_rate"), original_rise);
    resolved->SetNumberField(TEXT("original_steering_fall_rate"), original_fall);
    resolved->SetStringField(TEXT("angle_convention"), TEXT("nominal tire angle = inner front wheel; outer follows existing Ackermann"));
    FString text;
    FJsonSerializer::Serialize(resolved, TJsonWriterFactory<>::Create(&text));
    FFileHelper::SaveStringToFile(text, *config_->GetStringField(TEXT("resolved_path")));
    configured_ = true;
}

void ResearchSteering::observe(float dt)
{
    if (!config_.IsValid()) return;
    if (!configured_) configure();
    frame_dt_ = dt;
    elapsed_ += dt;
    if (!configured_) return;
    const double fl = -movement_->Wheels[0]->GetSteerAngle();
    const double fr = -movement_->Wheels[1]->GetSteerAngle();
    const double inner = std::abs(fl) >= std::abs(fr) ? fl : fr;
    telemetry_ << elapsed_ << ',' << dt << ',' << request_ << ',' << state_.position << ','
        << state_.velocity << ',' << fl << ',' << fr << ',' << geometry_.handwheel(inner) << '\n';
    if (elapsed_ - last_flush_ >= .5) { telemetry_.flush(); last_flush_ = elapsed_; }
}

float ResearchSteering::apply(float normalized)
{
    if (!config_.IsValid() || !configured_) return normalized;
    request_ = std::round(-FMath::Clamp(double(normalized), -1.0, 1.0)*state_.limit/resolution_)*resolution_;
    if (passthrough_) { state_.position = request_; return normalized; }
    if (frame_dt_ > 0) {
        state_.step(request_, frame_dt_);
        frame_dt_ = 0; // Multiple calls in one frame must not advance physical time twice.
    }
    if (geometry_.points.empty()) return -state_.position / state_.limit;
    return -geometry_.tire(state_.position) / geometry_.tire_limit(state_.limit);
}

void ResearchSteering::reset()
{
    state_.reset(); request_ = 0; frame_dt_ = 0;
}
