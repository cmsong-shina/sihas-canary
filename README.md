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

> Zeroconf를 사용한 등록으로 변경되었습니다. `configuration.yaml`을 사용하여 수동으로 등록하는 방법은 [v1.0.2](https://github.com/cmsong-shina/sihas-canary/tree/v1.0.2)를 참조하세요.



## Custom Component 설치

1. custom_components 폴더에 integration 다운로드

   ```bash
   cd <config_dir>/custom_components && git clone https://github.com/cmsong-shina/sihas-canary.git sihas_canary
   ```

2. configuration.yaml 수정

   [장치별 설정](#예시) 참조

   ```bash
   vim ../../configuration.yaml
   ```

3. HA 재시작



### 업데이트

#### 최신 버전으로 업데이트

```bash
cd <config_dir>/custom_components/sihas_canary && git pull
```

#### 특정 버전으로 변경

```bash
$ git tag
v1.0.0
v1.0.1
v1.0.2

$ git checkout v1.0.0
```



## 앱에서 로컬 통신 활성화

> 주의: 신뢰 할 수 있는 네트워크에서만 Home Assistant 연동을 사용하세요.

앱 → 장치 상세 화면 → 설정 속성 → 장치 정보 페이지로 이동 후 아래 설정을 수행합니다.

* 펌웨어 버전을 최신 버전으로 업데이트
* HA 설정을 활성화



## 통합 구성요소 찾기

`홈어시스턴트 웹` → `구성하기` → `통합 구성요소`에 나타난 장치를 설정 합니다.

나타나는 장치가 없을 경우, [mDNS 관련 문제](#mDNS-관련-문제)를 참조하세요.



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





# Known issue

#### mDNS 관련 문제

펌웨어에서 사용중인 라이브러리가 mDNS 다중 서비스 검색을 지원하지 않습니다.

단일 서비스 검색을 수행하기 위해 [avahi](https://www.avahi.org/) 혹은 [파이썬 스크립트](https://github.com/jstasiak/python-zeroconf)를 사용하여 등록할 수 있습니다.

```bash
$ avahi-browse _sihas._tcp
+ wlp3s0 IPv4 sihas_acm_abcdef                              _sihas._tcp          local
```

```python
from zeroconf import ServiceBrowser, Zeroconf


class MyListener:
    def remove_service(self, zeroconf, type, name):
        print("Service %s removed" % (name,))

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        print("Service %s added, service info: %s" % (name, info))


zeroconf = Zeroconf()
listener = MyListener()
browser = ServiceBrowser(zeroconf, ["_sihas._tcp.local."], listener)
try:
    input("Press enter to exit...\n\n")
finally:
    zeroconf.close()

```
