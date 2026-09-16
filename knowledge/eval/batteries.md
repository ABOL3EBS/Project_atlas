# Battery Technologies

## Lithium-ion chemistries

Lithium-ion cells dominate portable and grid storage because of their energy density.
NMC (nickel manganese cobalt) cells offer the best balance of capacity and power and
are common in electric vehicles. LFP (lithium iron phosphate) cells have lower energy
density but significantly longer cycle life and better thermal stability, which is why
they are preferred for stationary storage. Each chemistry has a nominal cell voltage
near 3.6 volts, but the discharge curves differ substantially at low state of charge.

## Lead-acid behavior

Lead-acid batteries remain the cheapest entry point for standby power. Flooded cells
require regular topping-up with distilled water and must be kept away from sparks
because they emit hydrogen while charging. Sealed absorbed glass mat (AGM) and gel
cells avoid maintenance but tolerate fewer charge cycles. As a rule of thumb, lead-acid
batteries should not be discharged below 50 percent state of charge, or the plates
sulfate and capacity permanently fades.

## Charge control

A charge controller sits between the energy source and the battery bank. PWM (pulse
width modulation) controllers are simple and cheap but waste the surplus voltage of a
solar array. MPPT (maximum power point tracking) controllers convert that surplus into
additional charge current and recover ten to thirty percent more energy. Bulk, absorption,
and float phases keep the voltage within the safe window for the chosen chemistry.

## Cycle life versus depth of discharge

Cycle life is strongly linked to how deeply a battery is discharged. An LFP cell rated
for six thousand cycles at 80 percent depth of discharge may deliver only one third of
those cycles if it is repeatedly drained to 100 percent. Shallow cycling, cool operating
temperatures, and a moderate charge current all extend service life. Temperature above
40 degrees Celsius accelerates electrolyte breakdown and reduces calendar life.

## Safety and thermal runaway

Thermal runaway begins when an internal short heats the cell beyond the separator's
melting point. NMC is more prone to it than LFP because of the lower decomposition
temperature. Battery management systems watch each cell voltage and temperature, balance
the cells, and disconnect the pack if any parameter leaves its safe range. In large
installations, cell spacing, insulation between packs, and fire suppression are designed
so a single failing module cannot cascade into the rest of the battery.

## Battery sizing and capacity

The usable capacity of a battery bank is not the same as its nameplate capacity.
Because depth of discharge is capped to protect cycle life, a bank rated for ten
kWh with a 50 percent DoD limit delivers only five kWh before the inverter calls for
a recharge. Capacity also shrinks with temperature and with age, so the industry
quotes capacity at 25 degrees and at a fresh cell. When sizing storage, multiply the
nighttime load by the number of autonomy days wanted and then divide by the allowed
depth of discharge to find the nameplate size.

## Nickel chemistry variations

Inside the NMC family the ratio of nickel, manganese, and cobalt changes the
behaviour. High-nickel formulations such as NMC 811 store more energy per kilogram
but have a lower thermal runaway threshold and shorter calendar life. Adding
manganese stabilises the lattice at the cost of some capacity. Cobalt-free chemistries
such as LFP sacrifice energy density for cost, safety, and longevity, which explains
their dominance in grid-scale systems where footprint matters less than lifecycle
cost.