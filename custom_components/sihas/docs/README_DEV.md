# SiHAS 개발 환경

## 시작

저장소 루트에서 실행합니다.

```bash
python3 scripts/ha_dev.py watch
```

최초 실행은 HA 이미지를 내려받고 `.ha-dev/config/configuration.yaml`을 생성합니다.

이후에는 기존 설정을 덮어쓰지 않습니다. HA 설정과 DB, 인증 정보는 Git에서 제외된
`.ha-dev/config`에 유지됩니다. `dev/configuration.yaml`은 최초 생성용 템플릿입니다.

`http://<Linux 호스트 IP>:8123`에서 초기 설정을 완료합니다.
`custom_components/sihas`는 컨테이너에 읽기 전용으로 직접 연결됩니다.
HACS 설치나 코드 복사, 이미지 재빌드는 필요하지 않습니다.

## DHCP로 장치 추가

Compose는 `network_mode: host`와 `NET_RAW`, `NET_ADMIN`을 사용합니다.
HA의 `default_config:`가 DHCP 검색을 활성화합니다. 이를 제거하는 경우 `dhcp:`를
명시적으로 추가해야 합니다. DHCP, mDNS(zeroconf), SiHAS 디버그 로그는 기본으로 켜져 있습니다.

## 수정과 자동 적용

`watch`는 `.py`, `.json`의 변경·추가·삭제를 감시합니다.

감시기는 한 터미널에서 하나만 실행합니다. Ctrl+C는 감시와 로그 출력을 종료하며 HA는 유지합니다.

```bash
python3 scripts/ha_dev.py up       # 감시 없이 시작
python3 scripts/ha_dev.py restart  # 수동 재시작
python3 scripts/ha_dev.py logs     # 로그 확인
python3 scripts/ha_dev.py down     # 개발용 컨테이너 종료·제거 (설정 데이터 유지)
```

설정 YAML을 바꾼 경우 수동으로 재시작합니다. Compose 설정 변경은 `up`으로 반영합니다.
IDE 중단점 디버깅은 이 구성에 포함되지 않습니다.

## 신규 장치 추가 시

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

## 버전 올리기

To modify `manifest.json` version field, use below command:

```bash
$ uvx bump-my-version show current_version
1.7.11

$ uvx bump-my-version show-bump
1.7.11 ── bump ─┬─ major ─ 2.0.0
                ├─ minor ─ 1.8.0
                ├─ patch ─ 1.7.12
                ├─ pre_l ─ invalid: The part has already the maximum value among ['b', 'final'] and cannot be bumped.
                ╰─ pre_n ─ 1.7.11-final2

$ uvx bump-my-version bump minor # [major|minor|patch]

$ uvx bump-my-version show current_version
1.8.0
```

`major`, `minor`, `patch`를 증가시키면 사전 릴리스를 거치지 않고 바로 정식 버전으로 올린다.
`pre_l`의 `first_value = "final"` 설정으로 이 동작을 기본값으로 사용한다.
예를 들어 `1.7.11`에서 `uvx bump-my-version bump major`를 실행하면 `2.0.0`이 된다.

베타 릴리스가 필요하면 시작 버전을 명시한 뒤 다음 순서로 진행한다.

```bash
uvx bump-my-version bump patch --new-version 1.7.12-b1
uvx bump-my-version bump pre_n  # 1.7.12-b2
uvx bump-my-version bump pre_n  # 1.7.12-b3
uvx bump-my-version bump pre_l  # 1.7.12 (정식 릴리스)
```

미리 확인하려면 `bump` 명령에 `--dry-run --verbose`를 추가한다.

푸시와 GitHub Release 생성은 별도로 수행한다. 아래 태그는 실제 생성한 버전으로 바꾼다.

GitHub에서 해당 태그로 Release를 생성하면 된다.
