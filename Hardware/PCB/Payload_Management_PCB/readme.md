# Payload Management PCB
This is an esp-32 based management pcb, we made it ourselves in kicad.
---
## Function
This PCB is designed to do 3 things
a) Detect which payload is connected via nfc
b) Provide power to the payload (has a mosfet to start/stop power when needed)
c) Help the PI5: It basically is designed to offload micro tasks from the pi5, so the pi5 can focus on object avoidance. It handles NFC module identification, manages power routing, and filters raw sensor data before passing clean data to the pi5
---
## Components
It uses an ESP32 S3 MINI 1U as the microcontroller. See BOM for more clarity
---
We added all the production files in the production folder. 
