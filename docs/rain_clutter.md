# Rain clutter at 77 GHz

Every drop in the beam returns an echo, and at 77 GHz rain can stand well above
the receiver noise over much of a radar's range. This page builds a model of
that return in steps. So far it covers rain's **reflectivity**, how strongly a
unit volume of rain backscatters, and the drops' **fall speeds**, which will
shape rain's Doppler spectrum. Both are in `radarperf.rain`.

Still to come are the clutter volume that a radar's beams and range cells cut
out of the rain, rain's Doppler spectrum, and how the engine uses them. Until
then, the `Rain` environment's clutter is the placeholder that
[losses.md](losses.md#propagation) describes, and it does not use this page's
reflectivity. The literature survey [7] collects the sources such a model draws
on.

## Reflectivity

Rain's volume reflectivity is the radar cross section per unit volume, summed
over the drop sizes:

```
eta = ∫ N(D) sigma_b(D) dD      [m⁻¹]
```

`N(D) dD` is the number of drops per cubic metre with diameters between `D`
and `D + dD`, and `sigma_b(D)` is one drop's monostatic radar cross section. A
target of RCS `sigma` and a resolution volume `V` of rain then compete as
`sigma` against `eta V`. The volume is the subject of a later step.

Weather radars at centimetre wavelengths take the drops as Rayleigh
scatterers, `sigma_b = pi⁵ |K|² D⁶ / lambda⁴` with `K = (m² − 1)/(m² + 2)` for
a refractive index `m`. That turns `eta` into `pi⁵ |K|² Z / lambda⁴`, with the
reflectivity factor `Z = ∫ N(D) D⁶ dD`, and leads to Z–R relations such as
`Z = 200 R^1.6`. At 77 GHz the wavelength is 3.9 mm. A 2 mm drop has the size
parameter `x = pi D / lambda = 1.6` and is far from small, so `sigma_b` has to
come from Mie scattering.

### The drop sizes

`radarperf.rain.marshall_palmer_dsd` is the exponential distribution of
Marshall and Palmer [3], equations (1)–(3):

```
N(D) = N_0 exp(−Lambda D),   N_0 = 0.08 cm⁻⁴ = 8000 m⁻³ mm⁻¹,
Lambda = 41 R^−0.21 cm⁻¹ = 4.1 R^−0.21 mm⁻¹
```

for a rain rate `R` in mm/h. Integrating `D⁶` over it gives
`Z = N_0 6! / Lambda⁷ = 296 R^1.47`, the entry in their Table 1 "from
equations (1) and (3)". The same table lists `Z = 220 R^1.60` as the revision
of their measured relation. The `200 R^1.6` usually called the Marshall–Palmer
relation is not in that paper.

### One drop

`radarperf.rain.mie_efficiencies` sums the Mie series for a sphere. With the
coefficients `a_n` and `b_n` as Mätzler [2] gives them, after Bohren and
Huffman:

```
Q_ext = (2/x²) Σ (2n+1) Re(a_n + b_n)
Q_sca = (2/x²) Σ (2n+1) (|a_n|² + |b_n|²)
Q_b   = (1/x²) |Σ (2n+1) (−1)ⁿ (a_n − b_n)|²
```

The radar cross section is `sigma_b = Q_b pi D² / 4`, and the extinction cross
section is `Q_ext pi D² / 4`. In the small-sphere limit `Q_b` tends to
`4 x⁴ |K|²`, which is the Rayleigh cross section above. The series stops after
`x + 4 x^(1/3) + 2` terms, the logarithmic derivative of `psi_n(m x)` comes from
downward recurrence, and the Riccati–Bessel functions of `x` from SciPy. The
tests reproduce Mätzler's example (`m = 5 + 0.4i`, `x = 1`: `Q_ext = 1.9794`,
`Q_sca = 0.8795`, `Q_b = 1.1138` [2], Section 4.1) and the Rayleigh limits of
`Q_b` and of absorption.

The refractive index is `m = sqrt(eps)`. `radarperf.rain.water_permittivity`
is the double Debye model of Liebe, Hufford and Manabe [1], equations (1) and
(4)–(4b), with `theta = 1 − 300/(273.15 + T)`:

```
eps(f) = (eps_0 − eps_1)/(1 − i f/gamma_1) + (eps_1 − eps_2)/(1 − i f/gamma_2) + eps_2
eps_0 = 77.66 − 103.3 theta,   eps_1 = 0.0671 eps_0,   eps_2 = 3.52 + 7.52 theta
gamma_1 = 20.20 + 146.4 theta + 316 theta² GHz,   gamma_2 = 39.8 gamma_1
```

At 77 GHz and 10 °C this gives `eps = 7.61 + 12.85i`, `m = 3.36 + 1.91i` and
`|K|² = 0.811`, against 0.931 at 3 GHz. The imaginary part is positive, the
sign of Liebe's `1 − i f/gamma` and of the absorbing `m = n + ik` that the Mie
series takes. The survey [7] notes that a 1993 revision of the model differs,
so the version matters when comparing with other computations.

### Rain's reflectivity

`radarperf.rain.rain_scattering` integrates the cross sections over the
distribution by the midpoint rule, in steps of 0.01 mm up to 10 mm. Halving the
step changes `eta` by less than 10⁻⁹ dB, and stopping at 8 mm changes it by
less than 0.001 dB at 100 mm/h. At 77 GHz and 10 °C
(`examples/rain_reflectivity.py` prints these tables):

| Rain rate | η | 10 log₁₀ η | Z_e | 200 R^1.6 | 130 R^0.65 [5] |
|---:|---:|---:|---:|---:|---:|
| 1 mm/h | 1.05 × 10⁻⁴ m⁻¹ | −39.8 dB | 19.3 dBZ | 23.0 dBZ | 21.1 dBZ |
| 2 mm/h | 1.92 × 10⁻⁴ m⁻¹ | −37.2 dB | 21.9 dBZ | 27.8 dBZ | 23.1 dBZ |
| 5 mm/h | 3.94 × 10⁻⁴ m⁻¹ | −34.0 dB | 25.0 dBZ | 34.2 dBZ | 25.7 dBZ |
| 10 mm/h | 6.43 × 10⁻⁴ m⁻¹ | −31.9 dB | 27.2 dBZ | 39.0 dBZ | 27.6 dBZ |
| 20 mm/h | 1.01 × 10⁻³ m⁻¹ | −30.0 dB | 29.1 dBZ | 43.8 dBZ | 29.6 dBZ |
| 25 mm/h | 1.16 × 10⁻³ m⁻¹ | −29.4 dB | 29.7 dBZ | 45.4 dBZ | 30.2 dBZ |
| 50 mm/h | 1.75 × 10⁻³ m⁻¹ | −27.6 dB | 31.5 dBZ | 50.2 dBZ | 32.2 dBZ |
| 100 mm/h | 2.58 × 10⁻³ m⁻¹ | −25.9 dB | 33.2 dBZ | 55.0 dBZ | 34.1 dBZ |

`Z_e` is the equivalent reflectivity factor, `lambda⁴ eta / (pi⁵ |K|²)`
with the conventional `|K|² = 0.93`: the `Z` that Rayleigh scatterers would
need for the same `eta`. Against it:

- `200 R^1.6`, the placeholder's reflectivity, overstates `eta` by 3.7 dB at
  1 mm/h, 11.9 dB at 10 mm/h and 21.8 dB at 100 mm/h, by these computations.
- Bertoldo et al.'s 77 GHz fit [5], also Mie scattering over Marshall–Palmer
  drops, lies 0.5 to 1.9 dB above `Z_e`. They do not state the `|K|²` of their
  equation (2). With 0.811, the value at 77 GHz, `Z_e` rises by 0.6 dB, and
  the fit then lies between 0.1 dB below and 1.3 dB above it.
- The survey [7] computes `eta` under the same assumptions and gets the same
  values, within 0.012 dB at its six rain rates.

Water warms from 0 to 20 °C: compared with 10 °C, `eta` is 0.55 to 0.63 dB
lower at 0 °C and 0.40 to 0.45 dB higher at 20 °C. Across 76–81 GHz it falls
by 0.07 dB at 10 mm/h.

## Attenuation and fall speeds

The same integral over the extinction cross section gives the one-way specific
attenuation, `10 log₁₀(e) · 1000 ∫ N(D) C_ext(D) dD` in dB/km. The second
table compares it with ITU-R P.838-3 [6] for horizontal polarization, which is
what the toolbox uses for attenuation:

| Rain rate | Attenuation, Mie | P.838-3 | Fall speed, mean | RMS | Water flux |
|---:|---:|---:|---:|---:|---:|
| 1 mm/h | 1.08 dB/km | 1.13 dB/km | 4.13 m/s | 4.24 m/s | 1.18 mm/h |
| 2 mm/h | 2.00 dB/km | 1.86 dB/km | 4.29 m/s | 4.40 m/s | 2.37 mm/h |
| 5 mm/h | 4.27 dB/km | 3.59 dB/km | 4.51 m/s | 4.62 m/s | 5.9 mm/h |
| 10 mm/h | 7.34 dB/km | 5.91 dB/km | 4.68 m/s | 4.81 m/s | 11.6 mm/h |
| 20 mm/h | 12.33 dB/km | 9.72 dB/km | 4.88 m/s | 5.03 m/s | 22.8 mm/h |
| 25 mm/h | 14.49 dB/km | 11.41 dB/km | 4.95 m/s | 5.11 m/s | 28.2 mm/h |
| 50 mm/h | 23.68 dB/km | 18.76 dB/km | 5.19 m/s | 5.38 m/s | 54.7 mm/h |
| 100 mm/h | 38.05 dB/km | 30.85 dB/km | 5.48 m/s | 5.69 m/s | 105 mm/h |

The Mie computation is 4 % below P.838-3 at 1 mm/h, 8 % above at 2 mm/h and
19 to 27 % above from 5 to 100 mm/h. The extinction is a different moment of
the same drop population as the backscatter. The difference shows how much the
answer depends on the distribution, which Marshall and Palmer tie to the rain
rate alone.

The fall speeds come from Tsikoudi et al. [4], equation (7), which they
attribute to Frisch et al. (1995) and Atlas et al. (1973). For `D` in metres
and speeds in m/s, it reads:

```
1.2·10⁸ (D/2)²            D < 0.11 mm
8333 (D/2) − 0.0833       0.11 mm ≤ D ≤ 0.86 mm
9.65 − 10.3 exp(−600 D)   D > 0.86 mm
```

The speeds scale by `(rho_0/rho)^0.4` for an air density `rho` below the
sea-level `rho_0` (`air_density_ratio`). The table weights each diameter by its
share of `eta`, as a Doppler spectrum weights it. A line of sight at
elevation `epsilon` sees a drop falling at `v` move at `−v sin(epsilon)`,
approaching when the radar looks up. A horizontal line of sight sees none of
it.

The water flux is the rain rate that the drop sizes carry at those speeds,
`(pi/6) ∫ D³ N(D) v(D) dD`. It comes out 5 to 18 % above the rain rate the
distribution was set for. The tables keep the nominal rate, as the survey [7]
does, rather than renormalizing the distribution.

## Where it breaks down

- **The distribution.** Marshall–Palmer is one empirical distribution, set by
  the rain rate alone. Their own observations fall short of it below about
  1.5 mm [3], and real rain varies from storm to storm. The attenuation's
  departure from P.838-3 above gives a sense of what that does to a moment of
  the distribution. The reflectivity at a given rain rate is therefore less
  certain than the integration is accurate.
- **Spheres.** Large drops flatten as they fall, and Tsikoudi et al. [4] model
  their axis ratios to get polarimetric quantities at 94 GHz. Spheres leave out
  any dependence on polarization.
- **Single scattering.** Each drop is lit by the incident wave alone, and the
  drops' echoes add in power. Over a path deep in heavy rain the attenuation
  reaches several nepers: the table's 38 dB/km at 100 mm/h is 8.8 Np/km.
  There, power scattered more than once can add to the return, and the model
  leaves it out.
- **Temperature.** The drops are taken at one temperature; the table above
  shows what 10 °C either way does.
- **Validation.** No measurement here confirms `eta` at 77 GHz. The 77 GHz
  measurements the survey [7] lists report detections after a sensor's
  processing, not `eta`.

## References

1. H. J. Liebe, G. A. Hufford and T. Manabe, "A model for the complex
   permittivity of water at frequencies below 1 THz", *International Journal
   of Infrared and Millimeter Waves*, vol. 12, no. 7, pp. 659–675, 1991,
   equation (1), p. 661, and equations (4)–(4b), p. 668,
   <https://its.ntia.gov/publications/download/LiebeHuffordManabe1991.pdf>.
2. C. Mätzler, *MATLAB functions for Mie scattering and absorption*, Research
   Report 2002-08, Institute of Applied Physics, University of Bern, June 2002,
   Section 2 (the efficiencies) and Section 4.1, printed p. 14 (the example),
   <https://omlc.org/software/mie/maetzlermie/Maetzler2002.pdf>.
3. J. S. Marshall and W. McK. Palmer, "The distribution of raindrops with
   size", *Journal of Meteorology*, vol. 5, pp. 165–166, August 1948,
   equations (1)–(3) and Table 1, p. 165.
4. I. Tsikoudi, A. Battaglia, C. Unal and E. Marinou, "Simulations of spectral
   polarimetric variables measured in rain at W-band", *Atmospheric
   Measurement Techniques*, vol. 18, pp. 4857–4870, 2025, equation (7),
   p. 4861, <https://doi.org/10.5194/amt-18-4857-2025>.
5. S. Bertoldo, C. Lucianaz and M. Allegretti, "On the use of a 77 GHz
   automotive radar as a microwave rain gauge", *Engineering, Technology &
   Applied Science Research*, vol. 8, no. 1, pp. 2356–2360, 2018, equations (2)
   and (5), p. 2358,
   <https://etasr.com/index.php/ETASR/article/download/1755/pdf/4515>.
6. ITU-R P.838-3 (03/2005), *Specific attenuation model for rain for use in
   prediction methods*, <https://www.itu.int/rec/R-REC-P.838>; implemented in
   `radarperf.itu.rain_coefficients`.
7. *Rain-clutter returns for 77 GHz FMCW radar: levels, Doppler spectra,
   fluctuations, and source traceability*, version 1.0, 14 October 2026,
   [references/rain_clutter_77ghz_reference.pdf](references/rain_clutter_77ghz_reference.pdf).
   A literature survey compiled with ChatGPT Pro: a guide to the primary
   sources, not a source of numbers.
