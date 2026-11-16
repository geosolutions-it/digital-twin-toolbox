# Jobs and batches

A **job** runs one workflow on one file. A **batch** runs a workflow on every supported file in a folder of the bucket, and combines the results into a single tileset.

## Organize the files

The **Assets** page browses the bucket. To create a folder, click **Upload** and type it in **Destination folder**, e.g. `my-city/`.

Group the files you want to process together in the same folder, for example one folder per city or per survey. A batch processes the folder and all its subfolders.

Results are written to the `output/` folder of the bucket. Batches never pick up files from there.

## Process a single file

1. In **Assets**, click **Process** next to the file. The button only appears for files the toolbox recognizes.
2. Set the options. The workflow is chosen from the file type: a point layer opens [Point instance](./workflows/point-instance), and for a polygon layer you pick [Polygon](./workflows/polygon) or [Buildings](./workflows/buildings).
3. Click **Process**. The job starts immediately.

## Process a folder

1. In **Assets**, click **Batch** next to the folder.
2. Pick the **Workflow** and set its options.
3. Click **Create jobs**. One job per file starts immediately.

Every job of a batch runs the picked workflow with the same options. Only the files that workflow accepts are included, see the Input section of its page; the others are skipped.

For a folder with mixed data, create one batch per workflow. [Buildings](./workflows/buildings) is not available in batches.

## Follow the progress

The **Pipelines** page lists single jobs and batches. Expand a batch to see its jobs.

| Status | Meaning |
| --- | --- |
| `READY` | created, not run yet |
| `PENDING` | queued or running |
| `SUCCESS` | the tileset is ready |
| `FAILURE` | the job failed, its log says why |
| `REVOKED` | the job was cancelled |

**Logs** on a job opens its log, which follows the steps while it runs and keeps the error when it fails.

## Combined tileset

When every job of a batch has finished, successfully or not, the toolbox builds a combined tileset that references all the successful ones. It is rebuilt automatically when a job of the batch is deleted.

Use **Rebuild combined tileset** after re-running some of the jobs.

## Actions

Each job and each batch has its own actions: run again or cancel, adjust parameters, download, delete. On a batch they apply to all its jobs, and download gives the combined tileset. Deleting also removes the output from the bucket.

**Adjust parameters** opens the options again: **Save** keeps them for the next run, **Save & run** re-runs straight away.

To act on many jobs at once, select them with the checkboxes.

## See the results

Open **Map** to see every successful tileset and terrain on a 3D globe.
