# A500 measurement hardware

## CIA configuration reported 2026-10-23

The measurement A500 has one CIA replaced with a chip from another Amiga 500.
The owner reported these current package markings; line breaks and spelling
are preserved below.

| Position | Package markings | Note |
|---|---|---|
| ODD CIA (CIA-A, `$bfe001` register base) | `C= CSG` / `8520` / `A-1` / `2689 24` | `A-1` is written on the right of the package. |
| EVEN CIA (CIA-B, `$bfd000` register base) | `MOS` / `8520A-1` / `0988 24` | As reported by the owner. |

The owner confirmed that both the replacement and a subsequent swap of the
CIAs between positions happened years before this measurement project began.
The configuration above therefore applies throughout our measurements; neither
operation occurred between capture sessions.

The MOS chip is probably the donor part: the donor A500 still has one MOS CIA
installed. This identification is the owner's inference, not a confirmed chip
history. The original replacement position is not established after the swap.
These are package markings, not independently verified internal silicon
revisions; the numeric codes are not decoded here.

Link this record from future capture metadata as the reported CIA configuration,
alongside the test ROM hash, other hardware settings, capture method and
repeatability evidence. For historical captures from this A500, this dated owner
confirmation supplies supplemental provenance; preserve the original immutable
reference manifests and packets.
