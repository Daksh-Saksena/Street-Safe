# Assembly Instructions
## Pre Requisites 
-> All parts printed  \
-> all PCBs assembled \
-> The BOTWING 60A esc (or similar) \
-> FlySky i6 Radio (or similar)  \
-> Raspberry PI 5 \
-> Everything else in the BOM \
---
## Step 1: Main Frame
So start with the main frame. The side where the footprint is angular is the front side, while the rounded part is the back. \
You will see 2 cut outs there. The one towards the front is for the PN432 NFC and the one near the back is for the payload PCB. \
Wire up the pogo pins and nfc to the payload pcb as per the schematics and wiring diagrams. \
Screw in the Landing gear at the bottom
\
Screw in the motor mounts and then the motors, make sure to put the wires into the pipes (may be hard). You will probably have to extend the wires. \
Then add the battery mount and the battery. (Note: the battery mount only works for the specific battery in the bom. If you change the battery, you have to change the mount) \
---
## Step 2: Electronics Shelf
Add the PI5 towaeds the back, and the FC + ESC towards the front on top of each other. Screw in and Wire things up as per the diagram. \
You must use metallic screws for the fc + esc, your fc wont be grounded otherwise. \ 
Add the PI5  active cooler ontop of the pi5. 
---
## Step 3: Waterproof Cover
Tape the picam to the hole at the front. Wire it up as needed. Add the LIDAR on top in its compartment, and in the gps box add the gps and rc, and wire them up.
---
## Step 4: Assembly
Add 55mm 3.5mm diameter alumiunium/nylon standoffs to the bottom of the main frame. Then add the electronics shelf on top of the battery holder. \
Add the waterproof cover on top (make sure its screwed in). 

You should be done!



