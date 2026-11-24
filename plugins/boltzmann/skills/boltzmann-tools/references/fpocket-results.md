# Binding Site Prediction (fpocket): inputs and results

Exact job name: `Binding_Site_Prediction`. Read the complete request and file
contract in `modules/small-molecule-toolbox.md` before submitting.

## Input and submission

`experiment_data.pdb_path` accepts a documented PDB ID, AlphaFold UniProt ID,
or an uploaded `.pdb` platform reference. A public PDB ID such as `6NZP` is an
inline value, not a local file requiring upload. Use the user's supplied ID;
do not ask for it again. If preflight reports only a missing upload receipt for
that explicitly requested, documented inline ID, the request already establishes
its provenance; `allow_partial_validation: true` acknowledges that limitation.
This does not authorize arbitrary platform references or bypass validation errors.

```json
{
  "job_name": "Binding_Site_Prediction",
  "experiment_data": {"pdb_path": "6NZP"},
  "allow_partial_validation": true
}
```

This is a recorded test input, not a default for other users' experiments.
Use `boltzmann_submit` once, keep its returned experiment name and `doc_id`, and
call `boltzmann_status` with that same ID and exact job name.

## Returned output

The successful status response contains an `OutputData` object:

| Key | Meaning and handling |
|---|---|
| `pockets_data` | Per-pocket records. The observed response includes pocket centers, radius, bounding-box size/center, `Source_Pocket_ID`, `Geometry_Schema_Version`, pocket PDB references, sequence highlights and residue identifiers. Preserve identifiers and their association with each pocket. |
| `outcsv_path` | Artifact object for the pocket statistics CSV. |
| `pdb_path` | Artifact object for the returned protein PDB. This is an output field, distinct from the request's `pdb_path`. |
| `pockets_zip_path` | **New output artifact:** ZIP containing the returned pocket PDB files. It is not a submission parameter and does not replace the other outputs. |

Each of the three artifact objects has `path` (platform storage reference) and
`download_link` (an array of signed download URLs). For the new archive:

```json
{
  "pockets_zip_path": {
    "path": "<storage reference from this job>",
    "download_link": ["<fresh signed URL from this job>"]
  }
}
```

1. Preserve all returned output fields. Use
   `OutputData.pockets_zip_path.download_link` for the archive; do not build a URL
   from the storage path or reuse links from a prior experiment.
2. Download through `boltzmann_download(download_url=..., output_folder=...)`.
   The helper takes one URL per call. Retain the CSV and protein PDB as well when
   the user requests complete results.
3. Signed URLs expire. Refresh `boltzmann_status` for the same job to obtain new
   links; do not resubmit the experiment to renew a download.
4. Inspect ZIP integrity and entries, and compare the pocket PDB filenames with
   the CSV and `pockets_data`. Report actual counts rather than assuming 15
   pockets or a fixed archive filename for every protein. Inspect members before
   extracting; never write an archive entry outside the destination directory.
5. If the archive field/link is missing or its download fails, report that
   artifact as unavailable while preserving any other retrieved outputs. Do not
   invent a link or classify all computation as failed solely on that basis.

The connector also exposes the artifact storage references in `gcp_paths`;
these are not signed download URLs. Pocket predictions and druggability scores
are computational estimates, not experimental confirmation of binding.

## Live verification: 2026-11-24

One authorized native-connector run with `pdb_path: "6NZP"` completed with
`status: "Success"`; the service reported 52 seconds. The fetched status included
all four `OutputData` keys above. All three downloadable artifacts were retrieved.

- The pocket ZIP contained 15 PDB files, `pocket1_atm.pdb` through
  `pocket15_atm.pdb`; its ZIP integrity check passed.
- `pockets_data` contained 15 pocket entries, and the statistics CSV had 15 rows.
- Observed CSV columns: `Pockets`, `GCP_Path`, `Druggability_Score`,
  `Pocket_Residues`, `Center_Coordinates`, `Max_Radius`.

These counts describe this verification run, not a required output count.
User-specific storage paths, job identifiers and expiring signed URLs are not
embedded in the shared skill.
