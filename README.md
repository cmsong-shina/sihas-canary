# SiHAS Canary

[TOC]

# 지원장치

* ACM-300: 에어컨 제어기
* AQM-300: 공기질 측정기
* CCM-300: 스마트 콘센트
* HCM-300: 온도 조절기
* SBM-300: 조명 스위치(버튼형)
* STM-300: 조명 스위치(터치형)





# 설정

## 앱에서 로컬 통신 활성화

> 주의: 신뢰 할 수 있는 네트워크에서만 Home Assistant 연동을 사용하세요.

앱 → 장치 상세 화면 → 설정 속성 → 장치 정보 페이지로 이동 후

* 펌웨어 버전을 최신 버전으로 업데이트 후

* HA 설정을 활성화 합니다.



## IP 고정 할당

공유기에서 해당 장치에 고정 IP를 할당 합니다.



## configuration.yaml 에 장치 추가

다음과 같은 구성을 추가합니다. 필요한 정보는 장치 정보 페이지에서 찾을 수 있습니다

```yaml
<base_entity>:
  - platform: sihas_canary
    type: <type_of_device>
    ip: <ip>
    mac: <mac>
    cfg: <cfg>
    # scan_interval: 10
```

* **필수**
  * `<base_entity>`: climate, light, switch 등. 하기 [장치 목록](#장치 목록) 참조.

  * `<type_of_device>`: ACM, STM 등. 하기 [장치 목록](#장치 목록) 참조.

  * `<ip>`: 장치에 할당한 고정 IP
    예) `192.168.1.101 `

  * `<mac>`: 장치 맥주소, `:`로 구분된 12자리 16진수 문자열, 소문자

    예) `a8:2b:d6:12:34:56`

  * `<cfg>`: 앱 → 장치 정보 → 컨피그에서 확인 가능한 장치 설정값, 숫자

* **선택**

  * `<scan-interval>`: 업데이트 주기(초), 2~10 사이로 설정 권장, 미설정시 기본값 30초([HA spec 참조](https://www.home-assistant.io/docs/configuration/platform_options#scan-interval))



### 장치 목록

#### Climate

* `ACM`
* `HCM`



#### Light

* `STM`
* `SBM`



#### Switch

* `CCM`



#### 예시

```yaml
# sihas_canary integration
switch:
  #CCM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: CCM
    cfg: 1

light:
  #STM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: STM
    cfg: 3

  #SBM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: SBM
    cfg: 1

climate:
  # HCM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: HCM
    cfg: 0
    scan_interval: 10

  # ACM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: ACM
    cfg: 1
    scan_interval: 10

sensor:
  # PMM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: PMM
    cfg: 0
    scan_interval: 10

  # AQM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: AQM
    cfg: 0
    scan_interval: 10
```



## Custom Component 설치

1. custom_components 폴더에 integration 다운로드

   ```bash
   cd <config_dir>/custom_components && git clone TODO: add proper link
   ```

2. configuration.yaml 수정

   [장치별 설정](#예시) 참조

   ```bash
   vim ../../configuration.yaml
   ```

3. HA 재시작

   ```bash
   sudo systemctl restart hass
   ```





# QnA

## Q. 상태는 업데이트 되는데 제어는 안돼요

펌웨어가 낮거나 Modbus 기능이 활성화 되지 않았을 경우 발생합니다.

앱 → 장치화면 → 설정 속성 → 장치 정보에서 펌웨어 버전을 최신으로 올려주시고 HA 설정이 활성화 되어있는지 확인해주세요.



## Q. ModbusNotEnabled 에러가 발생합니다.

Modbus 기능이 활성화 되지 않았을 경우 발생합니다.

앱 → 장치화면 → 설정 속성 → 장치 정보에서 HA 설정이 활성화 되어있는지 확인해주세요.



## Q. timeout 에러가 발생합니다

로그에 다음과 같은 에러가 발생 할 경우 장치의 IP가 올바로 설정 되어 있는지 확인해주세요.

가급적 장치에 고정 IP를 부여하는 것이 좋습니다.

```
2021-10-12 14:42:32 INFO (SyncWorker_7) [custom_components.sihas_canary.sihas_base] timeout on <AQM, 192.168.1.1>
```

