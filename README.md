# SiHAS Canary

[TOC]


# 개요

[시하스](https://sihas.co.kr/)to[HA](https://www.home-assistant.io/) 연동을 위한 컴포넌트입니다.



# 지원장치

* ACM-300: 에어컨 제어기
* AQM-300: 공기질 측정기
* CCM-300: 스마트 콘센트
* HCM-300: 온도 조절기
* SBM-300: 조명 스위치(버튼형)
* PMM-300: 스마트 전력 미터
* STM-300: 조명 스위치(터치형)



# 설정

## 앱에서 로컬 통신 활성화

> 주의: 신뢰 할 수 있는 네트워크에서만 Home Assistant 연동을 사용하세요.

앱 → 장치 상세 화면 → 설정 속성 → 장치 정보 페이지로 이동 후 아래 설정을 수행합니다.

* 펌웨어 버전을 최신 버전으로 업데이트

* HA 설정을 활성화



## IP 고정 할당

공유기에서 해당 장치에 고정 IP를 할당 합니다.



## configuration.yaml 에 장치 추가

다음과 같은 구성을 추가합니다. 필요한 정보는 앱 → 장치 정보 페이지에서 찾을 수 있습니다.

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

  * `<base_entity>`: climate, light, switch 등. 하기 [장치목록](#장치목록) 참조.

  * `<type_of_device>`: ACM, STM 등. 하기 [장치목록](#장치목록) 참조.

  * `<ip>`: 장치에 할당한 고정 IP

    > NOTE: 앱이 아닌 공유기에서 확인하는것이 정확합니다. (서버 통신시 업데이트가 되지 않음)

    예) `192.168.1.101 `

  * `<mac>`: 장치 맥주소, `:`로 구분된 12자리 16진수 문자열, 소문자

    예) `a8:2b:d6:12:34:56`

  * `<cfg>`: 앱 → 장치 정보 → 컨피그에서 확인 가능한 장치 설정값, 숫자

* **선택**

  * `<scan-interval>`: 업데이트 주기(초), 3~10 사이로 설정 권장, 미설정시 기본값 30초([HA spec 참조](https://www.home-assistant.io/docs/configuration/platform_options#scan-interval))



### 장치목록

#### Climate

* `ACM`
* `HCM`



#### Light

* `STM`
* `SBM`



#### Switch

* `CCM`



#### Sensor

* `AQM`
* `PMM`



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
    scan_interval: 3

  #SBM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: SBM
    cfg: 1
    scan_interval: 3

climate:
  # HCM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: HCM
    cfg: 0
    scan_interval: 4

  # ACM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: ACM
    cfg: 1
    scan_interval: 4

sensor:
  # PMM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: PMM
    cfg: 0
    scan_interval: 15

  # AQM
  - platform: sihas_canary
    ip: 192.168.1.1
    mac: a8:2b:d6:12:34:56
    type: AQM
    cfg: 0
    scan_interval: 15
```



## Custom Component 설치

1. custom_components 폴더에 integration 다운로드

   ```bash
   cd <config_dir>/custom_components && git clone https://github.com/cmsong-shina/sihas-canary.git
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



# 업데이트

```bash
cd <config_dir>/custom_components && git pull
```



# QnA

## Q. 상태는 업데이트 되는데 제어가 되지 않습니다.

펌웨어가 낮거나 HA 설정이 활성화 되지 않았을 경우 발생합니다.

앱 → 장치화면 → 설정 속성 → 장치 정보에서 펌웨어 버전을 최신으로 올려주시고 HA 설정이 활성화 되어있는지 확인해주세요.



## Q. ModbusNotEnabled 에러가 발생합니다.

HA 설정이 활성화 되지 않았을 경우 발생합니다.

앱 → 장치화면 → 설정 속성 → 장치 정보에서 HA 설정이 활성화 되어있는지 확인해주세요.



## Q. timeout 에러가 발생합니다.

HA 설정여부와 장치의 IP가 올바르게 설정 되어 있는지 확인해주세요.

가급적 장치에 고정 IP를 부여하는 것이 좋습니다.



## Q. 앱에서 HA 설정이 확인중에서 바뀌지 않습니다.

장치 펌웨어를 업데이트 해주세요.