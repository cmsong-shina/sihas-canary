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

## HomeAssistant workspace

[Linux - Home Assistant](https://www.home-assistant.io/installation/linux#install-home-assistant-core)

1. 레포지토리 클론

2. venv 초기화/활성화

    ```bash
    # venv 초기화
    $ python3 -m venv .

    # (필요할 경우) venv 활성화
    $ ./bin/activate
    ```

3. 의존성 설치

    `pyproject.toml`에 명시된 의존성을 설치해야 한다.

    ```bash
    $ pip3 install toml && python -c '
    import toml;
    c = toml.load("pyproject.toml")
    deps = c["project"]["dependencies"]
    deps = [dep.split("==")[0].split(">=")[0].strip() for dep in deps]
    print("\n".join(deps))
    ' | pip3 install -r /dev/stdin
    ```

    [참조한 스크립트](https://github.com/pypa/pip/issues/8049#issuecomment-633845028)

4. 커스텀 컴포넌트로 설치

    ```bash
    $ mkdir -p config/custom_components
    $ ln -s  $(realpath ../../sihas_canary/custom_components/sihas) config/custom_components/
    ```

5. launch.json 수정

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


##  Components workspace

Create `.env` on root path to intellisence.

```bash
$ echo 'PYTHONPATH=$PYTHONPATH:../../../' > .env
```



## 디버그 로깅

Home Assistant의 [Logger](https://www.home-assistant.io/integrations/logger/) Integration을 참조한다.

```yaml
logger:
  default: info
  logs:
    homeassistant.components.dhcp: debug
    homeassistant.components.zeroconf: debug
```


## 데이터 삭제(초기화)

```bash
$ rm -rf config/home-assistant_v2.db* config/.storage

# 혹은 tracking 중이지 않은 모든 파일을 삭제
$ git clean -dfX
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

# Prune data

`hass/core/config/home-assistant_v2.d` 삭제