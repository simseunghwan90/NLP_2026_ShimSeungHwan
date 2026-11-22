#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>
#include <vector>

// Post-actuator geometry only. The actuator state remains in CAN handwheel degrees.
class SteeringGeometry {
public:
    double ratio = 12.6;
    std::vector<std::pair<double, double>> points;
    void validate(double limit) const {
        if (!std::isfinite(ratio) || ratio <= 0) throw std::runtime_error("Invalid steering ratio");
        if (points.empty()) return;
        if (points.size() < 3 || points.front().first != -limit || points.back().first != limit)
            throw std::runtime_error("Geometry must cover fixed handwheel limits");
        for (size_t i = 0; i < points.size(); ++i) {
            const auto& p = points[i];
            if (!std::isfinite(p.first) || !std::isfinite(p.second) || std::abs(p.second) >= 30 ||
                (i && (p.first <= points[i-1].first || p.second <= points[i-1].second)))
                throw std::runtime_error("Invalid monotone steering geometry");
        }
        if (points.front().second >= 0 || points.back().second <= 0)
            throw std::runtime_error("Geometry must include straight ahead");
    }
    double tire(double h) const { return points.empty() ? h / ratio : interpolate(h, false); }
    double handwheel(double a) const { return points.empty() ? a * ratio : interpolate(a, true); }
    double tire_limit(double h_limit) const { return std::max(std::abs(tire(-h_limit)), std::abs(tire(h_limit))); }
private:
    double interpolate(double x, bool inverse) const {
        auto xval = [inverse](const std::pair<double,double>& p) { return inverse ? p.second : p.first; };
        auto yval = [inverse](const std::pair<double,double>& p) { return inverse ? p.first : p.second; };
        if (x <= xval(points.front())) return yval(points.front());
        for (size_t i=1; i<points.size(); ++i) {
            if (x <= xval(points[i])) {
                const double k = (x-xval(points[i-1])) / (xval(points[i])-xval(points[i-1]));
                return yval(points[i-1]) + k*(yval(points[i])-yval(points[i-1]));
            }
        }
        return yval(points.back());
    }
};
