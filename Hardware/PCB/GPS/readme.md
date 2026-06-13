# GPS PCB

Sooo this is the gps pcb, we made it ourselves in kicad. 

---

## Function
Accurate gps to provide the mission software real time GPS locations to an accuracy of about 1.5m. It also has a compass to tell the software where the drone is pointed.

---

## Components
So the raw GPS module is the uBlox SAM m10q.  
The compass is the IST 8310 module.  
*See bom for more clarity.*

---

We added all the production files in the production folder. I tried to add as many file types as possible so that anyone who needs it can get it easily.

--- 

# Assembly Instructions
1.  **Solder Paste Application:** It is highly recommended to use a laser-cut stainless steel **solder stencil** rather than manual hand-pasting to prevent solder bridging across close-proximity components.
2.  **Component Placement:** Carefully place the surface-mount devices (SMDs), taking extra care with the orientation of the SAM-M10Q patch antenna and the IST8310 alignment dot.
3.  **Reflow Method:** Utilize a temperature-controlled SMD hotplate or reflow oven for assembly. If you are new to hotplate soldering, review proper thermal profiling guidelines to avoid overheating the sensitive internal RF shielding of the GPS receiver.
