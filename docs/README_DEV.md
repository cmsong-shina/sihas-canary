Just to memo for me :D


#### To bump version

Modify `manifest.json` version with result of below command

```bash
$ standard-version # for check, run with `--dry-run` option
✔ bumping version in manifest.json from 1.0.2 to 1.0.3
```

To enter develop env:
```bash
$ source /home/maya/workspace/hass/core/venv/bin/activate
$ hass -c  config
```

Create `.env` on root path to intellisence
```bash
$ echo 'PYTHONPATH=$PYTHONPATH:../../../' > .env
```