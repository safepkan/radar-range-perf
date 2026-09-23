"""Independent synthetic checks of FFT power and common-phase estimation."""

from __future__ import annotations

import numpy as np
from scipy.signal import get_window


def main() -> None:
    rng = np.random.default_rng(20260922)
    nc, ns, nrx, count = 1024, 512, 8, 12
    amplitude, noise_std, phase_std = 500.0, 10.0, 0.005
    wr = np.asarray(get_window("blackmanharris", ns))
    wd = np.asarray(get_window("hann", nc))
    carrier_bin = 23
    fast_phase = 2 * np.pi * carrier_bin * np.arange(ns) / ns
    channel_phase = np.arange(nrx) * 0.7
    tone = np.exp(-1j * fast_phase) * wr / wr.sum()
    t = np.linspace(-1, 1, nc)
    polynomial = np.polynomial.polynomial.polyvander(t, 3)
    projector = np.linalg.pinv(polynomial)
    fd = np.fft.fftfreq(nc, 15.96e-6)
    keep = abs(fd) > 5000
    background = 0.0
    common = 0.0
    enbw = nc * np.sum(wd**2) / wd.sum() ** 2
    for _ in range(count):
        phase = rng.normal(0, phase_std, size=nc)
        x = amplitude * np.cos(
            fast_phase[None, :, None]
            + channel_phase[None, None, :]
            + phase[:, None, None]
        )
        x += rng.normal(0, noise_std, size=x.shape)
        rd = np.fft.fft(np.fft.rfft(x[:, :, 0] * wr, axis=1) * wd[:, None], axis=0) / (
            wr.sum() * wd.sum()
        )
        background += float(np.mean(abs(rd[keep, 80:120]) ** 2)) / count
        gain = np.einsum("csr,s->cr", x, tone)
        measured_phase = np.unwrap(np.angle(gain), axis=0)
        measured_phase -= polynomial @ (projector @ measured_phase)
        f = np.fft.fft(measured_phase * wd[:, None], axis=0) / wd.sum()
        cross = (abs(f.sum(axis=1)) ** 2 - np.sum(abs(f) ** 2, axis=1)) / (
            nrx * (nrx - 1)
        )
        common += float(np.mean(cross[keep])) / count
    expected_background = (
        noise_std**2 * np.sum(wr**2) / wr.sum() ** 2 * np.sum(wd**2) / wd.sum() ** 2
    )
    expected_common = phase_std**2 * enbw / nc
    assert abs(background / expected_background - 1) < 0.03
    assert abs(common / expected_common - 1) < 0.06
    print(
        f"White-noise FFT power / theoretical expectation: {background/expected_background:.4f}"
    )
    print(
        f"Recovered common phase power / injected expectation: {common/expected_common:.4f}"
    )


if __name__ == "__main__":
    main()
