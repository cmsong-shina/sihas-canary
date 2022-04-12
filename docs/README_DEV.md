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

> INFO  
> Follow below command when host does not have compatible version of python. (Debian)
> ```bash
> $ sudo update-alternatives --install /usr/bin/python3 python3 <binary: path> <int: priority>
> ```
>
> Below shows in case you have multiple version(3.8, 3.9) and `python3` linked to 3.9, to change 3.8.
> ```bash
> $ sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 3
> $ sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 2
> ```

# 개발환경 설정
Create `.env` on root path to intellisence
```bash
$ echo 'PYTHONPATH=$PYTHONPATH:../../../' > .env
```