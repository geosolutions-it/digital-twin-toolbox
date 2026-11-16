# Getting started

Run the toolbox on your machine and convert a first point cloud to 3D Tiles.

## Requirements

- [Docker Engine](https://docs.docker.com/engine/install/) with the Compose plugin
- Git
- Linux, macOS, or Windows with WSL2

::: tip Windows
Clone with `core.autocrlf=false` as shown below, the shell scripts must keep `LF` line endings.
:::

## 1. Get the code

```bash
git clone -c core.autocrlf=false https://github.com/geosolutions-it/digital-twin-toolbox
cd digital-twin-toolbox
```

To run a specific release, check out its tag, for example `git checkout v1.0.0`. The list is on the [releases page](https://github.com/geosolutions-it/digital-twin-toolbox/releases).

## 2. Create the configuration

```bash
./scripts/init-env.sh
```

This creates the `.env` file from `.env.copy` and generates the passwords and storage keys. The defaults work for a local run.

## 3. Start the stack

```bash
docker compose up -d
```

The first start pulls the images and takes a few minutes. When it is done, open [http://localhost](http://localhost).

## 4. Upload a point cloud

In the application, open **Assets** and click **Upload**. Choose a LAS or LAZ file of your own and upload it. The file must declare its CRS.

The other kinds of data follow the same steps, see the [workflows](./introduction#workflows).

## 5. Convert it

1. In **Assets**, click **Process** next to the file.
2. Keep the default options and click **Process**.
3. Open **Pipelines**. The job runs in the background, its status turns to `SUCCESS` when the tileset is ready.

## 6. See the result

- Open **Map** to see it in 3D, together with your other results.
- Click **Download 3D Tiles** on the job to get the tileset as files.
- Click **Open tileset** to get the `tileset.json` URL, for loading it in another viewer.

## Stop the stack

```bash
docker compose down
```

Uploaded files and results stay in `data/`. Add `-v` to also delete the job history.
