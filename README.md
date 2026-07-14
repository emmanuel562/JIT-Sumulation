JIT — Just In Time
Retrofit AEB for Legacy Commercial Vehicles
By Team Axora

What is JIT?
JIT (Just In Time) is an aftermarket Automatic Emergency Braking system designed to be installed on commercial vehicles already on the road — buses, trucks, and danfos — that were never built with active safety systems.
Nigeria loses tens of thousands of lives to road crashes every year. The vast majority are attributable to human error. The existing fleet cannot wait for a new-vehicle turnover cycle. JIT retrofits the solution onto the vehicles that are already out there.

How it works
JIT uses a 77GHz mmWave radar as its primary sensor, paired with a camera, IMU, and rain sensor, to calculate a dynamic Time-to-Collision threshold in real time. When a collision risk is detected, the system escalates through three intervention levels — Forward Collision Warning, Demand Braking Support, and Critical Intervention Braking — before physically actuating a lead screw mechanism against the brake pedal.
All safety-critical logic runs on an STM32 microcontroller. A secondary Qualcomm processor handles mid-range optical context at 30fps. The two communicate over a defined interface with explicit timeout and fallback rules.

Project status
This repository is under active development. The team is currently building toward a simulation-stage demonstration using Wokwi (firmware logic) and Webots (visual environment).
Hardware prototype and field validation are subsequent milestones.

Repository structure
(To be populated as the codebase develops)

Team
Team Axora

Emmanuel — Project Lead
Abdulbasit — Technical Co-Lead


Licence
(To be decided)
