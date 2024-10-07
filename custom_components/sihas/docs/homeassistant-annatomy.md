# Discovery

## Zeroconf

각각 다음 함수에 중단점을 걸어서 확인하자.

`homeassistant/components/zeroconf/__init__.py`의 `async_process_client()`


## DHCP

설정법은 [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/#dhcp) 문서를 참조하자.

DHCP의 경우 aiodhcpwatcher 패키지를 사용하는데, `homeassistant/components/dhcp/__init__.py`의 `async_process_client()`에 중단점을 걸고 보면 편하다.


DHCP의 경우 문서에는 없지만 matcher를 소문자로 적어야 한다.

`WatcherBase.async_process_client()` 함수를 보면 다음 구문처럼 소문자 hostname과 matcher를 비교한다.

```py
if (
    matcher_hostname := matcher.get(HOSTNAME)
) is not None and not _memorized_fnmatch(
    lowercase_hostname, matcher_hostname
):
    continue
```
