#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>

// Optional effective turning-creep loss. Inputs are native states and accepted
// commands only. No measured trajectory, session identifier or time schedule.
inline double poweredCreepLoss(double amplitude, double curvature, double speed,
                              double acc, double brake, double zero_speed = 0.6, double rise_speed = 0)
{
    if (!std::isfinite(amplitude) || amplitude < 0 || amplitude > 15)
        throw std::runtime_error("Invalid powered creep resistance");
    if (!std::isfinite(zero_speed) || zero_speed < 0.2 || zero_speed > 0.8)
        throw std::runtime_error("Invalid powered creep fade speed");
    if (!std::isfinite(rise_speed) || (rise_speed != 0 && (rise_speed < 0.05 || rise_speed > 0.5 || rise_speed >= zero_speed)))
        throw std::runtime_error("Invalid powered creep rise speed");
    if (amplitude == 0 || acc <= 0 || acc >= 85 || brake > 0) return 0;
    if (!std::isfinite(curvature) || !std::isfinite(speed))
        throw std::runtime_error("Invalid native creep state");
    const double k = std::min(1.0, std::abs(curvature) / 0.07);
    const double velocity_weight = std::max(0.0, std::min(1.0, (zero_speed - std::abs(speed)) / (zero_speed - 0.15)));
    const double pedal_weight = std::min(1.0, (85.0 - acc) / 2.0);
    const double original = amplitude * k * k * velocity_weight * pedal_weight;
    return rise_speed > 0 ? original * std::min(1.0, std::abs(speed) / rise_speed) : original;
}
