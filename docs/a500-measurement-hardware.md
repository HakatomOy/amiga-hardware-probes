# A500 measurement hardware

## CIA configuration reported 2026-10-23

The measurement A500 has one CIA replaced with a chip from another Amiga 500.
The owner reported these current package markings; line breaks and spelling
are preserved below.

| Position | Package markings | Note |
|---|---|---|
| ODD CIA (CIA-A, `$bfe001` register base) | `C= CSG` / `8520` / `A-1` / `2689 24` | `A-1` is written on the right of the package. |
| EVEN CIA (CIA-B, `$bfd000` register base) | `MOS` / `8520A-1` / `0988 24` | As reported by the owner. |

Which position received the replacement, and when it was installed relative to
historical captures, have not been established. Do not infer either from the
different manufacturer markings. These are package markings, not independently
verified internal silicon revisions; the numeric codes are not decoded here.

Link this record from future capture metadata as the reported CIA configuration,
alongside the test ROM hash, other hardware settings, capture method and
repeatability evidence. Do not silently assign it retroactively to immutable
reference captures whose hardware provenance was not recorded.
