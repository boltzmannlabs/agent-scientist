# Finished-figure audit

Compare the final figure with the source paper and its legend:

- [ ] Species, charges, and protonation states match the source; every step, including catalyst/cofactor regeneration, is shown. [features: always]
- [ ] Each curved arrow runs from the donor atom/bond to the target atom/bond, and its head matches one- or two-electron movement. [features: curved]
- [ ] All stereocenters and specified double-bond geometries match the source; the drawing is not inverted into its mirror image. [features: stereo]
- [ ] Residue names, numbers, and chain identifiers match the source and use a single consistent code style. [features: residues]
- [ ] All radicals, coordination bonds, oxidation states, and isotopes from the source are shown; explicit H atoms match the source and the input's `keep_h` settings. [features: radicals,metals,isotopes,explicit_h]
- [ ] All automated checks and positive controls pass, with no visible overlaps or clipping at final size. [features: always]
- [ ] Atom numbers and single charges sit in open space beside their respective atoms; single charges on structures follow the figure-wide circle setting, while ions and multiple charges use superscripts; bond lengths are uniform and arrows are black. [features: numbers,charges,bonds,arrows]
- [ ] When requested, TS structures are enclosed in brackets with ‡, and forming/breaking or partial bonds use the chosen dotted or dashed style. [features: ts]
- [ ] The handover includes `.cdxml`, `.svg`, and `.png` files, plus a 2–4 line caption stating the mechanism's certainty and source and defining all abbreviations. [features: always]
- [ ] Preferred: each arrow tail sits directly on its drawn lone pair, unpaired electron, or bond. [features: curved]
