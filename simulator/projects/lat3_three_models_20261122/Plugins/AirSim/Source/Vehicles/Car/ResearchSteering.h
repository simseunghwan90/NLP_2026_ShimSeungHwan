#pragma once
#include "CoreMinimal.h"
#include "SteeringDynamics.h"
#include "SteeringGeometry.h"
#include <fstream>

class UWheeledVehicleMovementComponent;

// Optional native plant; normalized input is negative CAN handwheel / 150.
class ResearchSteering {
public:
    explicit ResearchSteering(UWheeledVehicleMovementComponent* movement);
    void observe(float dt);
    float apply(float normalized);
    void reset();
private:
    UWheeledVehicleMovementComponent* movement_;
    TSharedPtr<FJsonObject> config_;
    SteeringDynamics state_;
    SteeringGeometry geometry_;
    std::ofstream telemetry_;
    bool configured_ = false;
    bool passthrough_ = false;
    double ratio_ = 12.6, resolution_ = .1, frame_dt_ = 0, elapsed_ = 0, last_flush_ = 0;
    double request_ = 0;
    void configure();
};
