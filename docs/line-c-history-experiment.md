# Kind45 line-C history experiment

Kind45 isolates whether a prior normal-mode A/B/C DMA history changes the early line-mode BZERO samples. It reuses kind44's ten C/A presets, fixed phase-zero timing, direct and BBUSY-poll observer kernels at `$FF7600` and `$FF7700`, and eight consecutive DMACONR reads. The hardware-facing stimulus changes only the data written into the source buffers before the normal-mode prime.

The matrix contains 960 descriptors: 10 C/A presets x 6 history patterns x 2 observers x 8 repeats. Descriptor words are `(kind=45, preset, priming_pattern, phase=0, observer, repeat)`. Pattern indices and literal words are stored in the build manifest. The default pattern order ends in `all-ffff`, which allows the collection-done CCP check to confirm that both A and B retain eight `$FFFF` words. C memory is restored after priming to the selected first-C word followed by seven zero words, matching kind44's source image.

`none` skips the normal blit after setting all three source regions to zero. `all-zero` executes the real normal blit with zero words. The remaining controls execute the same blit after filling the A, B, and/or C source with eight `$FFFF` words. The blit uses BLTCON0 `$0FCA`, BLTCON1 zero, and BLTSIZE `$0088`; BBUSY is first observed set and then clear. The destination at `$17000` is cleared after priming. The line-mode trial then restores ADAT and CDAT, restores the line-mode register inputs, and starts the unchanged kind44 line blit and observer.

The archived source snapshot lists SHA-256 values for `build_line_c_history_rom.py`, `build_rom.py`, `run_rom.py`, every `src/rom` input, and every vendored RBCP source. `source_id` binds the descriptor table and literal preset tables to the assembled ROM. `run_rom.py` stores its binary hash and rejects a binary that changes during capture. Its `source-memory-check.json` records the final descriptor, expected bytes, actual bytes, and comparisons for all three source regions.

Build an immutable archive with:

```powershell
python build_line_c_history_rom.py --out build/line-c-history-v1
```

An exploratory subset can be built by naming patterns, for example:

```powershell
python build_line_c_history_rom.py --patterns a-ffff,b-ffff,all-ffff --out build/line-c-history-nonzero
```

Archive the output before running it on hardware. The complete matrix is 960 rows, below the 2560-row payload limit.
