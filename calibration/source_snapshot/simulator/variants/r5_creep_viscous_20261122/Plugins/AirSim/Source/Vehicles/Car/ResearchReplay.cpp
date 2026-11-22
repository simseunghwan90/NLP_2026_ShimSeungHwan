#include "ResearchReplay.h"
#include "PoweredLoss.h"
#include "PoweredCreep.h"
#include "CarPawn.h"
#include "WheeledVehicleMovementComponent4W.h"
#include "VehicleWheel.h"
#include "PhysXVehicleManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/PlatformMisc.h"
#include <iomanip>
#include <stdexcept>

ResearchReplay::ResearchReplay(ACarPawn* pawn, UWheeledVehicleMovementComponent* movement, const msr::airlib::WheelStates* reported)
    : pawn_(pawn), movement_(movement), reported_(reported)
{
    FString path, live_path;
    const bool replay = FParse::Value(FCommandLine::Get(), TEXT("ResearchReplay="), path);
    live_ = FParse::Value(FCommandLine::Get(), TEXT("ResearchVehicle="), live_path);
    if (replay && live_) throw std::runtime_error("Choose ResearchReplay or ResearchVehicle, not both");
    if (!replay && !live_) return;
    if (live_) path = live_path;
    FString text;
    if (!FFileHelper::LoadFileToString(text, *path) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(text), config_))
        throw std::runtime_error("Invalid ResearchReplay JSON");
    if (live_) {
        if (config_->GetBoolField(TEXT("lift")) || config_->HasField(TEXT("commands")))
            throw std::runtime_error("Live vehicle cannot use a lift fixture or recorded commands");
    }
    else {
        commands_ = config_->GetArrayField(TEXT("commands"));
        if (commands_.Num() == 0) throw std::runtime_error("Empty replay commands");
    }
    if (config_->HasField(TEXT("pedal_map"))) pedal_map_ = config_->GetArrayField(TEXT("pedal_map"));
    if (config_->HasField(TEXT("brake_map"))) brake_map_ = config_->GetArrayField(TEXT("brake_map"));
    poweredCreepLoss(number(TEXT("powered_creep_resistance_nm"), 0), 0, 0, 0, 0, number(TEXT("powered_creep_speed_zero_mps"), 0.6), number(TEXT("powered_creep_rise_speed_mps"), 0));
    if (config_->HasField(TEXT("powered_loss_map"))) {
        double previous=-1;
        for (const auto& value : config_->GetArrayField(TEXT("powered_loss_map"))) {
            const auto& point=value->AsArray();
            if (point.Num()!=2) throw std::runtime_error("Invalid powered loss knot");
            const double x=point[0]->AsNumber(), y=point[1]->AsNumber();
            if (!std::isfinite(x) || !std::isfinite(y) || x<0 || x<=previous || y<0 || y>20)
                throw std::runtime_error("Invalid powered loss map");
            powered_loss_map_.emplace_back(x,y); previous=x;
        }
        if (powered_loss_map_.size()<2 || powered_loss_map_.front().first!=0)
            throw std::runtime_error("Incomplete powered loss map");
    }
    duration_ = number(TEXT("duration_s"), 15);
    warmup_ = number(TEXT("warmup_s"), 2);
    telemetry_.open(TCHAR_TO_UTF8(*config_->GetStringField(TEXT("telemetry_path"))));
    if (!telemetry_) throw std::runtime_error("Cannot open replay telemetry");
    telemetry_ << std::setprecision(12)
        << "t_s,dt_s,acc_pct,brake_pct,throttle,brake,engine_rpm,fl_rpm,fr_rpm,rl_rpm,rr_rpm,fl_air,fr_air,rl_air,rr_air,x_m,y_m,z_m,speed_mps,gear,physx_throttle,physx_brake,sleeping,reported_rl_rpm,reported_rr_rpm,rear_x_m,rear_y_m,yaw_ue_deg,effective_rear_residual_nm,loss_curvature_per_m\n";
}

double ResearchReplay::number(const TCHAR* key, double fallback) const
{
    double value;
    return config_->TryGetNumberField(key, value) ? value : fallback;
}

double ResearchReplay::pedal(double pct) const
{
    if (pedal_map_.Num() == 0) return pct / 100.0;
    for (int i = 1; i < pedal_map_.Num(); ++i) {
        const auto& a = pedal_map_[i - 1]->AsArray();
        const auto& b = pedal_map_[i]->AsArray();
        if (pct <= b[0]->AsNumber()) {
            const double k = FMath::Clamp((pct - a[0]->AsNumber()) / (b[0]->AsNumber() - a[0]->AsNumber()), 0.0, 1.0);
            return a[1]->AsNumber() + k * (b[1]->AsNumber() - a[1]->AsNumber());
        }
    }
    return pedal_map_.Last()->AsArray()[1]->AsNumber();
}

double ResearchReplay::brake(double pct) const
{
    if (brake_map_.Num() == 0) return pct / 100.0;
    for (int i = 1; i < brake_map_.Num(); ++i) {
        const auto& a = brake_map_[i-1]->AsArray();
        const auto& b = brake_map_[i]->AsArray();
        if (pct <= b[0]->AsNumber()) {
            const double k = FMath::Clamp((pct-a[0]->AsNumber())/(b[0]->AsNumber()-a[0]->AsNumber()), 0.0, 1.0);
            return a[1]->AsNumber()+k*(b[1]->AsNumber()-a[1]->AsNumber());
        }
    }
    return brake_map_.Last()->AsArray()[1]->AsNumber();
}

void ResearchReplay::configure()
{
    auto* drive = static_cast<physx::PxVehicleDrive4W*>(movement_->PVehicle);
    auto* actor = drive->getRigidDynamicActor();
    // First allow the unmodified vehicle to settle, then support its chassis.
    // Pitch about the front axle, retaining front contact and rear suspension droop.
    if (config_->GetBoolField(TEXT("lift"))) {
        const float pitch = number(TEXT("lift_pitch_deg"), -12);
        const float height = 118.f * FMath::Sin(FMath::DegreesToRadians(-pitch))
            + number(TEXT("lift_height_adjust_cm"), 0);
        FRotator rotation = pawn_->GetActorRotation();
        rotation.Pitch += pitch;
        pawn_->SetActorLocationAndRotation(pawn_->GetActorLocation() + FVector(0, 0, height), rotation,
            false, nullptr, ETeleportType::TeleportPhysics);
        actor->setLinearVelocity(physx::PxVec3(0));
        actor->setAngularVelocity(physx::PxVec3(0));
        actor->setRigidDynamicLockFlags(physx::PxRigidDynamicLockFlag::eLOCK_LINEAR_X |
            physx::PxRigidDynamicLockFlag::eLOCK_LINEAR_Y | physx::PxRigidDynamicLockFlag::eLOCK_LINEAR_Z |
            physx::PxRigidDynamicLockFlag::eLOCK_ANGULAR_X | physx::PxRigidDynamicLockFlag::eLOCK_ANGULAR_Y |
            physx::PxRigidDynamicLockFlag::eLOCK_ANGULAR_Z);
        // A locked chassis has zero body kinetic energy even while wheels spin.
        // PhysX resets wheel/engine speeds when the body sleeps without throttle.
        // Keep this measurement fixture awake; do not alter ground vehicle sleep.
        actor->setSleepThreshold(0);
        actor->wakeUp();
    }
    origin_ = pawn_->GetActorLocation();
    auto engine = drive->mDriveSimData.getEngineData();
    engine.mMOI = number(TEXT("motor_moi_kg_m2"), engine.mMOI / 10000.0) * 10000;
    engine.mPeakTorque *= number(TEXT("torque_scale"), 1);
    if (config_->HasField(TEXT("torque_curve"))) {
        const auto& curve = config_->GetArrayField(TEXT("torque_curve"));
        engine.mMaxOmega = number(TEXT("motor_max_rpm"), 10000) * 2 * PI / 60;
        double peak = 0;
        for (auto& point : curve) peak = FMath::Max(peak, point->AsArray()[1]->AsNumber());
        engine.mPeakTorque = peak * 10000;
        engine.mTorqueCurve.clear();
        for (auto& point : curve) {
            const auto& p = point->AsArray();
            engine.mTorqueCurve.addPair(p[0]->AsNumber() * 2 * PI / 60 / engine.mMaxOmega, p[1]->AsNumber() / peak);
        }
    }
    drive->mDriveSimData.setEngineData(engine);
    if (config_->HasField(TEXT("low_speed_substeps"))) {
        drive->mWheelsSimData.setSubStepCount(drive->mWheelsSimData.getThresholdLongSpeed(),
            number(TEXT("low_speed_substeps"), 3), drive->mWheelsSimData.getHighForwardSpeedSubStepCount());
    }
    for (int i = 0; i < 4; ++i) {
        auto wheel = drive->mWheelsSimData.getWheelData(i);
        brake_max_[i] = wheel.mMaxBrakeTorque;
        if (i >= 2) {
            wheel.mMOI = number(TEXT("rear_wheel_moi_kg_m2"), wheel.mMOI / 10000.0) * 10000;
            wheel.mDampingRate = number(TEXT("rear_damping_nm_s"), wheel.mDampingRate / 10000.0) * 10000;
            rear_damping_[i - 2] = wheel.mDampingRate;
            drive->mWheelsSimData.setWheelData(i, wheel);
        }
    }
    // Persist actual PhysX quantities, including UE's cm^2 conversion.
    auto resolved = MakeShared<FJsonObject>();
    resolved->SetNumberField(TEXT("motor_moi_kg_m2"), engine.mMOI / 10000);
    resolved->SetNumberField(TEXT("peak_torque_nm"), engine.mPeakTorque / 10000);
    resolved->SetNumberField(TEXT("motor_max_rpm"), engine.mMaxOmega * 60 / (2 * PI));
    resolved->SetNumberField(TEXT("mass_kg"), actor->getMass());
    resolved->SetNumberField(TEXT("powered_residual_offset_nm"), number(TEXT("powered_residual_offset_nm"), 0));
    resolved->SetNumberField(TEXT("powered_creep_resistance_nm"), number(TEXT("powered_creep_resistance_nm"), 0));
    resolved->SetNumberField(TEXT("powered_creep_speed_zero_mps"), number(TEXT("powered_creep_speed_zero_mps"), 0.6));
    resolved->SetNumberField(TEXT("powered_creep_rise_speed_mps"), number(TEXT("powered_creep_rise_speed_mps"), 0));
    resolved->SetStringField(TEXT("powered_creep_rule"), TEXT("native speed full<=0.15m/s,linear fade to configured zero speed;curvature factor min(1,abs(k)/0.07)^2;powered only,fade83..85pct"));
    resolved->SetNumberField(TEXT("powered_curvature_loss_nm_m2"), number(TEXT("powered_curvature_loss_nm_m2"), 0));
    if (config_->HasField(TEXT("powered_loss_map")))
        resolved->SetArrayField(TEXT("powered_loss_map"), config_->GetArrayField(TEXT("powered_loss_map")));
    resolved->SetNumberField(TEXT("aero_drag_coefficient"), movement_->DragCoefficient);
    resolved->SetNumberField(TEXT("aero_chassis_width_m"), movement_->ChassisWidth / 100);
    resolved->SetNumberField(TEXT("aero_chassis_height_m"), movement_->ChassisHeight / 100);
    // Read-only audit: PhysX uses centimetres here; inertia has kg*cm^2 units.
    const auto com = actor->getCMassLocalPose().p;
    const auto inertia = actor->getMassSpaceInertiaTensor();
    resolved->SetNumberField(TEXT("com_local_x_m"), com.x / 100);
    resolved->SetNumberField(TEXT("com_local_y_m"), com.y / 100);
    resolved->SetNumberField(TEXT("com_local_z_m"), com.z / 100);
    resolved->SetNumberField(TEXT("inertia_principal_x_kg_m2"), inertia.x / 10000);
    resolved->SetNumberField(TEXT("inertia_principal_y_kg_m2"), inertia.y / 10000);
    resolved->SetNumberField(TEXT("inertia_principal_z_kg_m2"), inertia.z / 10000);
    resolved->SetStringField(TEXT("audit_frame"), TEXT("PhysX actor local: x forward, y right, z up; principal inertia in mass frame"));
    resolved->SetNumberField(TEXT("final_ratio"), drive->mDriveSimData.getGearsData().mFinalRatio);
    resolved->SetNumberField(TEXT("clutch_strength"), drive->mDriveSimData.getClutchData().mStrength);
    resolved->SetBoolField(TEXT("lift"), config_->GetBoolField(TEXT("lift")));
    resolved->SetStringField(TEXT("input_mode"), live_ ? TEXT("live_can_fraction") : TEXT("recorded_can"));
    for (const TCHAR* key : {TEXT("model_id"), TEXT("model_sha256")}) {
        FString value;
        if (config_->TryGetStringField(key, value)) resolved->SetStringField(key, value);
    }
    resolved->SetBoolField(TEXT("reverse_as_brake"), movement_->bReverseAsBrake);
    resolved->SetNumberField(TEXT("sleep_threshold"), actor->getSleepThreshold());
    resolved->SetNumberField(TEXT("low_speed_vehicle_substeps"), drive->mWheelsSimData.getLowForwardSpeedSubStepCount());
    resolved->SetNumberField(TEXT("high_speed_vehicle_substeps"), drive->mWheelsSimData.getHighForwardSpeedSubStepCount());
    resolved->SetNumberField(TEXT("vehicle_substep_threshold_mps"), drive->mWheelsSimData.getThresholdLongSpeed() / 100);
    TArray<TSharedPtr<FJsonValue>> wheels;
    for (int i = 0; i < 4; ++i) {
        const auto& w = drive->mWheelsSimData.getWheelData(i);
        auto j = MakeShared<FJsonObject>();
        j->SetNumberField(TEXT("moi_kg_m2"), w.mMOI / 10000);
        j->SetNumberField(TEXT("radius_m"), w.mRadius / 100);
        j->SetNumberField(TEXT("damping_nm_s"), w.mDampingRate / 10000);
        j->SetNumberField(TEXT("brake_max_nm"), w.mMaxBrakeTorque / 10000);
        const auto& suspension = drive->mWheelsSimData.getSuspensionData(i);
        const auto& tire = drive->mWheelsSimData.getTireData(i);
        j->SetNumberField(TEXT("wheel_mass_kg"), w.mMass);
        j->SetNumberField(TEXT("sprung_mass_kg"), suspension.mSprungMass);
        j->SetNumberField(TEXT("spring_strength_n_m"), suspension.mSpringStrength);
        j->SetNumberField(TEXT("spring_damper_n_s_m"), suspension.mSpringDamperRate);
        j->SetNumberField(TEXT("suspension_max_compression_m"), suspension.mMaxCompression / 100);
        j->SetNumberField(TEXT("suspension_max_droop_m"), suspension.mMaxDroop / 100);
        j->SetNumberField(TEXT("tire_lat_stiff_x"), tire.mLatStiffX);
        j->SetNumberField(TEXT("tire_lat_stiff_y"), tire.mLatStiffY);
        wheels.Add(MakeShared<FJsonValueObject>(j));
    }
    resolved->SetArrayField(TEXT("wheels"), wheels);
    FString text;
    FJsonSerializer::Serialize(resolved, TJsonWriterFactory<>::Create(&text));
    FFileHelper::SaveStringToFile(text, *config_->GetStringField(TEXT("resolved_path")));
    configured_ = true;
}

void ResearchReplay::observe(float dt)
{
    if (!enabled() || done_) return;
    elapsed_ += dt;
    if (!configured_ && elapsed_ >= warmup_ / 2) configure();
    const double t = elapsed_ - warmup_;
    if (t < 0 || !configured_) return;
    auto* drive = static_cast<physx::PxVehicleDrive4W*>(movement_->PVehicle);
    const FVector p = pawn_->GetActorLocation();
    const FVector rear = (movement_->Wheels[2]->Location + movement_->Wheels[3]->Location) / 2;
    telemetry_ << t << ',' << dt << ',' << acc_pct_ << ',' << brake_pct_ << ','
        << applied_.throttle << ',' << applied_.brake << ','
        << drive->mDriveDynData.getEngineRotationSpeed() * 60 / (2 * PI);
    for (int i = 0; i < 4; ++i)
        telemetry_ << ',' << drive->mWheelsDynData.getWheelRotationSpeed(i) * 60 / (2 * PI);
    for (int i = 0; i < 4; ++i) telemetry_ << ',' << movement_->Wheels[i]->IsInAir();
    telemetry_ << ',' << p.X / 100 << ',' << p.Y / 100 << ',' << p.Z / 100
        << ',' << movement_->GetForwardSpeed() / 100 << ',' << movement_->GetCurrentGear()
        << ',' << drive->mDriveDynData.getAnalogInput(physx::PxVehicleDrive4WControl::eANALOG_INPUT_ACCEL)
        << ',' << drive->mDriveDynData.getAnalogInput(physx::PxVehicleDrive4WControl::eANALOG_INPUT_BRAKE)
        << ',' << drive->getRigidDynamicActor()->isSleeping()
        << ',' << reported_->rl.rpm << ',' << reported_->rr.rpm
        << ',' << rear.X / 100 << ',' << rear.Y / 100 << ',' << pawn_->GetActorRotation().Yaw
        << ',' << effective_residual_ << ',' << loss_curvature_ << '\n';
    if (live_ && t - last_flush_ >= 1) {
        telemetry_.flush();
        last_flush_ = t;
    }
    if (!live_ && t >= duration_) {
        telemetry_.flush();
        done_ = true;
        FPlatformMisc::RequestExit(false);
    }
}

ResearchReplay::Controls ResearchReplay::controls(const Controls& original)
{
    if (!enabled()) return original;
    Controls c = live_ ? original : Controls();
    const double t = elapsed_ - warmup_;
    if (live_) {
        if (!configured_) return original;
        // The bridge passes CAN acceleration / 100 with no pedal correction.
        // Keep its steering, brake, handbrake and gear ownership unchanged.
        acc_pct_ = FMath::Clamp(double(original.throttle), 0.0, 1.0) * 100;
        brake_pct_ = original.brake * 100;
        c.throttle = pedal(acc_pct_);
        c.brake = brake(brake_pct_);
    }
    else {
        c.is_manual_gear = true;
        c.manual_gear = 1;
        c.gear_immediate = true;
        if (t < 0 || !configured_ || done_) { c.brake = 1; return c; }
        while (command_index_ + 1 < commands_.Num() && commands_[command_index_ + 1]->AsArray()[0]->AsNumber() <= t)
            ++command_index_;
        const auto& row = commands_[command_index_]->AsArray();
        // Rows: relative receive time, acc %, brake %, steering-wheel degrees, auto bits.
        const int flags = row[4]->AsNumber();
        acc_pct_ = flags & 4 ? row[1]->AsNumber() : 0;
        brake_pct_ = flags & 2 ? row[2]->AsNumber() : 0;
        c.throttle = pedal(acc_pct_);
        c.steering = flags & 1 ? -row[3]->AsNumber() / 7.5 / 20.0 : 0;
        c.brake = brake(brake_pct_);
    }
    double drag = number(TEXT("rear_residual_torque_nm"), 0);
    const double powered_offset = number(TEXT("powered_residual_offset_nm"), 0);
    const double powered_gain = number(TEXT("powered_curvature_loss_nm_m2"), 0);
    const double creep_amplitude = number(TEXT("powered_creep_resistance_nm"), 0);
    if (powered_offset != 0 || powered_gain != 0 || !powered_loss_map_.empty() || creep_amplitude > 0) {
        const double inner = FMath::Max(FMath::Abs(movement_->Wheels[0]->GetSteerAngle()),
                                      FMath::Abs(movement_->Wheels[1]->GetSteerAngle()));
        const double tangent = FMath::Tan(FMath::DegreesToRadians(inner));
        // Existing A1 axle geometry: wheelbase 2.36m, track 1.45m.
        loss_curvature_ = tangent / (2.36 + 0.725 * tangent);
        drag = poweredResidual(drag, powered_offset, powered_gain, loss_curvature_, acc_pct_ > 0 && brake_pct_ == 0);
        if (!powered_loss_map_.empty())
            drag=mappedPoweredResidual(number(TEXT("rear_residual_torque_nm"),0), powered_loss_map_, loss_curvature_, acc_pct_, brake_pct_);
        if (creep_amplitude > 0)
            drag += poweredCreepLoss(creep_amplitude, loss_curvature_, movement_->GetForwardSpeed() / 100.0, acc_pct_, brake_pct_, number(TEXT("powered_creep_speed_zero_mps"), 0.6), number(TEXT("powered_creep_rise_speed_mps"), 0));
    }
    effective_residual_ = drag;
    const double coast_damping = number(TEXT("rear_coast_damping_nm_s"), 0);
    if (drag > 0 || coast_damping > 0) {
        // Smooth Coulomb resistance in the wheel solver. PhysX service brakes
        // lock a zero-speed wheel regardless of drive torque, so cannot model
        // a residual resistance that the powered vehicle can overcome.
        // Below 0.05 rad/s (0.48 RPM), regularize to finite viscous damping.
        // This uses simulated speed only and preserves commanded service brake.
        for (int i = 2; i < 4; ++i) {
            auto wheel = movement_->PVehicle->mWheelsSimData.getWheelData(i);
            const float omega = FMath::Abs(movement_->PVehicle->mWheelsDynData.getWheelRotationSpeed(i));
            wheel.mDampingRate = rear_damping_[i - 2] + drag * 10000 / FMath::Max(omega, 0.05f)
                + (acc_pct_ == 0 ? coast_damping * 10000 : 0);
            movement_->PVehicle->mWheelsSimData.setWheelData(i, wheel);
        }
    }
    applied_ = c;
    return c;
}
