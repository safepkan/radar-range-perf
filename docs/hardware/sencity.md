# HUBER+SUHNER SENCITY radar antennas

The toolbox has presets for two of HUBER+SUHNER's SENCITY waveguide antennas,
which are made of metallized plastic and sit directly on the radar's PCB. This
page says what the presets hold, how to read the data sheets' efficiency
figures, and what a measurement showed. [losses.md](../losses.md) says where
the antenna terms enter the range equation.

| Preset | Antenna | Channels, polarization | MMIC interface | Boresight directivity | 10 dB beamwidth, azimuth and elevation |
|---|---|---|---|---|---|
| `antenna.sencity_farad_iv()` | FARAD-IV, art. 1377.99.0744 [1] | 8 TX, 8 RX, vertical | Infineon CTRX8191F and similar | about 15 dBi | about 94° and 30° |
| `antenna.sencity_this_ii()` | THIS-II, art. 1377.99.0701 [2] | 4 TX, 4 RX, horizontal | TI AWR2544 and similar | about 16 dBi | about 140° and 16° |

Both cover 76–81 GHz. The presets are digitised from the preliminary data
sheets' 77 GHz charts (`radarperf/data/sencity_farad_iv.csv` and
`sencity_this_ii.csv`): each is an `AntennaPair` of the per-channel average TX
and RX cuts, which are similar but not identical. The charts are for a PCB
mount without a radome. Their gains are directivities, so the antenna's loss
belongs in `SystemLosses.tx_antenna_loss_db` and `rx_antenna_loss_db`, and a
radome in `radome_one_way_loss_db`. The beamwidths above are the presets'.

## Efficiency and mismatch

Both data sheets give a radiation efficiency of at least 90 % (at most
0.46 dB) and a reflection coefficient of at most −10 dB, which allows a
mismatch loss of up to 0.46 dB [1, 2]. Counted separately, realized gain is
then at most 0.92 dB below the stated directivity. That is the bound to use for
`tx_antenna_loss_db` and `rx_antenna_loss_db` unless better data are at hand.

The data sheets do not define radiation efficiency. IEEE Std 145 [3] defines it
as the radiated power over the power the antenna accepts, which leaves mismatch
out; the 0.92 dB bound adds the two. HUBER+SUHNER's own papers on the same
metallized-plastic waveguide technology use the term for total efficiency,
which includes mismatch: one letter gives its 90 % as radiation efficiency in
the abstract and as total efficiency in the text [5]. Read that way, realized
gain is at most 0.46 dB below directivity. The papers' 76–81 GHz prototypes
reach total efficiencies of up to 94 % (0.27 dB) for eight-horn linear arrays,
measured from a WR-12 adapter at the antenna's PCB interface [4], and above
90 % (0.46 dB) for a slotted array [5]. They are not the SENCITY products, so
they show what the technology reaches, not what a given antenna does.

## Measured

The FARAD-IV is the antenna of Infineon's CARKIT evaluation radar, which the
CARKIT validation study measured [6]. On a turntable, the radar's two-way
azimuth response read 0.9, 2.5 and 4.7 dB down at 10, 15 and 20°, against 0.8,
2.5 and 4.5 dB on one side of the preset. In a measurement chamber the radar
came out 0.4–0.7 dB below a model with the antenna's directivity and no
hardware losses ([ctrx8188f.md: “Measured on one radar”](ctrx8188f.md#measured-on-one-radar)).
The loss of the radar's housing cover is unknown, so that figure does not
isolate the antenna's own loss.

## References

1. HUBER+SUHNER, SENCITY FARAD-IV Radar Antenna 1377.99.0744, preliminary data
   sheet, document PIM-P62799, 2026-01-20.
2. HUBER+SUHNER, SENCITY THIS-II Radar Antenna 1377.99.0701, preliminary data
   sheet, document PIM-P50871, 2025-12-12.
3. IEEE Std 145-2013, *IEEE Standard for Definitions of Terms for Antennas*:
   radiation efficiency, realized gain.
4. A. Garcia-Tejero, M. Burgos-Garcia and F. Merli, "Broadband metallized
   plastic waveguide antenna with robust isolation interface at 77 GHz",
   *IEEE Antennas and Wireless Propagation Letters*, vol. 23, no. 10,
   pp. 2875–2879, 2024, doi:10.1109/LAWP.2024.3412424. Prototypes made at
   HUBER+SUHNER; accepted version at <https://oa.upm.es/85665/>.
5. A. Garcia-Tejero, F. Rodríguez Varela, R. Torres-Sánchez, M. Burgos-Garcia
   and F. Merli, "Wideband untilted narrow wall slotted partially staggered
   waveguide array based on metallized molded plastic at E-band", *IEEE
   Antennas and Wireless Propagation Letters*, vol. 23, no. 3, pp. 915–919,
   2024, doi:10.1109/LAWP.2023.3337495. Accepted version at
   <https://oa.upm.es/85664/>.
6. CARKIT validation study, `studies/2026-09-11_carkit-validation/`:
   [NOTES.md](../../studies/2026-09-11_carkit-validation/NOTES.md),
   “Reflector” and “Sensitivity against the model”.
