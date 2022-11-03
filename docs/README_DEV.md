Just memo for me :D


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
>
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

VSCODE에서 실행시 DHCP Sniffing 권한을 위해서 `launch.json`을 수정한다.
```diff
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Home Assistant",
      "type": "python",
      "request": "launch",
      "module": "homeassistant",
      "justMyCode": false,
      "args": ["--debug", "-c", "config"],
+     "sudo": true
    },
    ...
}
```

# 신규 장치 추가 시
신규 플랫폼일 경우 `__init__.py`에 플랫폼을 추가한다.

```diff
PLATFORMS: list[str] = [
    "button",
    "climate",
+   "cover",
    "light",
    "sensor",
    "switch",
]
```


신규 장치일 경우 `const.py`에 장치 타입을 추가한다.

```diff
SUPPORT_DEVICE: Final[List[str]] = [
    "ACM",
    "AQM",
    "BCM",
    "CCM",
    "HCM",
    "PMM",
+   "RBM",
    "SBM",
    "STM",
]
```

# Clean
대규모 변경 사항이 있을 경우 기존 장치와 데이터를 삭제하고 다시 실행한다.

```bash
```