#pragma once
#include <algorithm>
#include <cmath>
#include <deque>
#include <stdexcept>
#include <utility>

// Degrees are physical handwheel degrees, independent of the upstream BSW map.
class SteeringDynamics {
public:
    double delay = 0, omega = 1, zeta = 1, rate_limit = 140, limit = 150;
    double position = 0, velocity = 0, target = 0, time = 0;

    void validate() const {
        if (!std::isfinite(delay) || !std::isfinite(omega) || !std::isfinite(zeta) ||
            !std::isfinite(rate_limit) || !std::isfinite(limit) ||
            delay < 0 || delay > 1 || omega <= 0 || omega > 100 ||
            zeta <= 0 || zeta > 3 || rate_limit <= 0 || rate_limit > 1000 || limit <= 0 || limit > 150)
            throw std::invalid_argument("Invalid physical steering parameters");
    }

    void reset(double initial = 0) {
        position = target = clamp(initial, -limit, limit);
        velocity = time = 0;
        pending.clear();
    }

    double step(double command, double dt) {
        if (!std::isfinite(command) || !std::isfinite(dt) || dt <= 0 || dt > 1)
            throw std::invalid_argument("Invalid steering command/timestep");
        pending.emplace_back(time + delay, clamp(command, -limit, limit));
        // <=1 ms numerical integration; no observed state is fed back into it.
        const int count = static_cast<int>(std::ceil(dt / .001));
        const double h = dt / count;
        for (int i = 0; i < count; ++i) {
            while (!pending.empty() && pending.front().first <= time + 1e-10) {
                target = pending.front().second;
                pending.pop_front();
            }
            const double acc = omega*omega*(target-position) - 2*zeta*omega*velocity;
            velocity = clamp(velocity + h*acc, -rate_limit, rate_limit);
            position += h*velocity;
            if (position >= limit) { position = limit; velocity = std::min(velocity, 0.0); }
            if (position <= -limit) { position = -limit; velocity = std::max(velocity, 0.0); }
            time += h;
        }
        return position;
    }

private:
    std::deque<std::pair<double, double>> pending;
    static double clamp(double x, double lo, double hi) { return std::max(lo, std::min(x, hi)); }
};
