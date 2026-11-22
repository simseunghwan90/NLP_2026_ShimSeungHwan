#pragma once

#include "CoreMinimal.h"
#include "vehicles/car/api/CarApiBase.hpp"
#include "physics/WheelStates.hpp"
#include <fstream>
#include <vector>
#include <utility>

class ACarPawn;
class UWheeledVehicleMovementComponent;

// Explicit post-CAN plant selection. Disabled unless a research option is given.
class ResearchReplay
{
public:
    using Controls = msr::airlib::CarApiBase::CarControls;
    ResearchReplay(ACarPawn* pawn, UWheeledVehicleMovementComponent* movement, const msr::airlib::WheelStates* reported);
    void observe(float dt);
    Controls controls(const Controls& original);
    bool enabled() const { return config_.IsValid(); }

private:
    double number(const TCHAR* key, double fallback) const;
    double pedal(double pct) const;
    double brake(double pct) const;
    void configure();
    ACarPawn* pawn_;
    UWheeledVehicleMovementComponent* movement_;
    const msr::airlib::WheelStates* reported_;
    TSharedPtr<FJsonObject> config_;
    TArray<TSharedPtr<FJsonValue>> commands_;
    TArray<TSharedPtr<FJsonValue>> pedal_map_;
    TArray<TSharedPtr<FJsonValue>> brake_map_;
    std::ofstream telemetry_;
    double elapsed_ = 0;
    double duration_ = 0;
    double warmup_ = 2;
    int command_index_ = 0;
    bool configured_ = false;
    bool done_ = false;
    bool live_ = false;
    double last_flush_ = 0;
    FVector origin_;
    float brake_max_[4] = {};
    float rear_damping_[2] = {};
    Controls applied_;
    double acc_pct_ = 0;
    double brake_pct_ = 0;
    double effective_residual_ = 0;
    double loss_curvature_ = 0;
    std::vector<std::pair<double,double>> powered_loss_map_;
};
