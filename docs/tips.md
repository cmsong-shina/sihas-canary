Integration은 device + service


전역적으로 HomeAssistant 인스턴스에 접근하고 싶으면 `core.async_get_hass()`를 사용  - [Globally available HomeAssistant object](https://developers.home-assistant.io/blog/2022/08/24/globally_accessible_hass)


`core/config/.storage`에 저장
    - `core.config_entries`: discovery 한 결과값 aka 실제 장치 정보
    - `core.entity_registry`: aka 가상 장치


Config Entry
    장치 발견 및 config.yaml에서 생성
    `core.config_entries`에 저장
    시작시 역직렬화되서 로드됨.



Component
    `custom component`

Platform
    Entity Platform
    Integration Platform
    Component가 포함 가능

Integration

Domain
    Name space of Integration

Add-on
    External software runs on docker

