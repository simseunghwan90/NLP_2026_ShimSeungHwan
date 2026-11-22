#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>
#include <utility>

// Effective powered rolling/drivetrain loss. Never uses observed vehicle states.
inline double poweredResidual(double base, double offset, double gain, double curvature, bool powered)
{
    if (!std::isfinite(base) || base < 0 || !std::isfinite(offset) ||
        !std::isfinite(gain) || gain < 0 || !std::isfinite(curvature))
        throw std::runtime_error("Invalid effective powered resistance");
    return powered ? std::max(0.0, base + offset + gain * curvature * curvature) : base;
}

inline double mappedPoweredResidual(double base, const std::vector<std::pair<double,double>>& map,
                                    double curvature, double acc, double brake)
{
    if (map.empty() || acc <= 0 || brake > 0 || acc >= 85) return base;
    const double x = std::abs(curvature);
    double target = map.back().second;
    for (size_t i=1; i<map.size(); ++i) {
        if (x <= map[i].first) {
            const double f=std::max(0.0,std::min(1.0,(x-map[i-1].first)/(map[i].first-map[i-1].first)));
            target=map[i-1].second+f*(map[i].second-map[i-1].second);
            break;
        }
    }
    const double weight=std::min(1.0,(85.0-acc)/2.0);
    return std::max(0.0,base+weight*(target-base));
}
