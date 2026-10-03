# Observations

## Task 1
루트 서버는 최종 IP가 아니라 다음에 물어볼 DNS 서버를 알려주었고, glue가 없으면 해당 네임서버의 주소를 먼저 찾아서 계속 진행했다.
직접 조회해 보니 www.korea.ac.kr은 3개의 서버를 거쳤고, www.microsoft.com은 10개의 서버를 거쳤다.

## Task 2
마지막 CNAME의 도메인이 원래 도메인과 다르면 서드파티로 판단했지만, wikipedia는 wikimedia.org와 운영 주체가 같아 잘못 판단되었다.
hotspot과 wifi에서 비교한 결과 CDN 사이트 10개 중 7개가 resolver나 네트워크에 따라 다른 IP를 보여 DNS steering이 일어날 수 있음을 확인했다.

## Task 3
기본 캐시는 실제 TTL 대신 60초로 고정해서, TTL이 짧으면 만료된 값을 사용하고 길면 너무 일찍 버려 불필요한 조회가 생겼다.
올바른 캐시의 최소 upstream query는 275번이며, TTL이 끝난 뒤에는 새 값을 받아야 하므로 이보다 줄일 수 없다. 특히 TTL이 20초이고 자주 조회되는 www.microsoft.com에서 문제가 가장 크게 나타났다.