# Bundled OpenMP runtime

`libgomp.so.1` is the GNU OpenMP runtime. LightGBM's compiled library (`lib_lightgbm.so`) links against it,
and Vercel's Python runtime does not ship it. `stackscope/analytics/salary_runtime.py` uses the system copy
when there is one and loads this file otherwise, before LightGBM.

| | |
|---|---|
| Package | `libgomp-8.5.0-28.el8_10.alma.1.x86_64.rpm` (AlmaLinux 8 BaseOS), unmodified `usr/lib64/libgomp.so.1.0.0` |
| Why this build | GCC 8.5 on glibc 2.28, the same baseline as LightGBM's `manylinux_2_28` wheel; requires only `GLIBC_2.17` and provides every `GOMP_*` symbol `lib_lightgbm.so` imports (up to `GOMP_4.5`) |
| RPM SHA-256 | `fba0574d69f6a946696c031e834312f428fe585a4a7842906fc4353ca317b6f0` (matches the repository metadata) |
| File SHA-256 | `e985bcbb6b444c2c472de70c331ab101e6de860affa3a20d1d1aecd06d9242e8` |
| Licence | GPLv3+ with the GCC Runtime Library Exception |
| Source | [`gcc-8.5.0-28.el8_10.alma.1.src.rpm`](https://vault.almalinux.org/8.10/BaseOS/Source/Packages/gcc-8.5.0-28.el8_10.alma.1.src.rpm) |
