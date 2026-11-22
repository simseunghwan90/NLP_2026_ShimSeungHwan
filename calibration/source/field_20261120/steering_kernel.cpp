// Fit and regress the actual ROS-free native plant, rather than a second implementation.
#include "SteeringDynamics.h"

extern "C" void rollout(const double* command, int n, double dt, double initial,
                         double delay, double omega, double zeta, double* output) {
    SteeringDynamics plant;
    plant.delay = delay;
    plant.omega = omega;
    plant.zeta = zeta;
    plant.rate_limit = 140;
    plant.limit = 150;
    plant.validate();
    plant.reset(initial);
    output[0] = plant.position;
    for (int i = 1; i < n; ++i)
        output[i] = plant.step(command[i - 1], dt);
}
