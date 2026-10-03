# Observations

## Task 1

루트 서버는 찾는 사이트의 IP 주소를 바로 알려주는 것이 아니라, 다음에 어떤 DNS 서버에 물어봐야 하는지 알려주었다. delegation에 glue A 레코드가 없으면 nameserver의 주소를 먼저 찾아본 뒤 원래 DNS 조회를 계속하도록 했다.
평소에는 내 컴퓨터가 resolver에 한 번 물어보면 되지만, 직접 DNS 서버를 따라가 보니 www.korea.ac.kr은 3개의 서버를 거쳤고 www.microsoft.com은 10개의 서버를 거쳤다.

## Task 2

Wireshark에서 확인해 보니 packet 2는 Answer가 0이고 Authority 부분에 NS 레코드가 있어서 다음 DNS 서버를 알려주는 delegation response였고, packet 6은 Answer 부분에 www.korea.ac.kr의 A 레코드가 있어서 최종 answer response였다.
나는 마지막 CNAME의 도메인이 원래 사이트의 도메인과 다르면 third-party라고 판단했다. 하지만 Wikipedia는 wikipedia.org에서 wikimedia.org로 이름이 달라지지만 같은 Wikimedia에서 운영하기 때문에 이 방법으로는 잘못 판단되었다.
hotspot과 wifi에서 DNS 결과를 비교했을 때 CDN을 사용하는 10개 사이트 중 7개에서 서로 다른 IP 주소가 나왔다. 따라서 DNS가 사용자에 따라 다른 서버를 알려줄 수 있다는 점은 확인했지만, IP가 다르다는 것만으로 그 서버가 실제로 더 가까운지는 알 수 없었다.

## Task 3

BaselineCache는 각 DNS 정보의 실제 TTL을 사용하지 않고 모두 60초 동안 저장하고 있었다. 그래서 TTL이 짧은 정보는 이미 만료됐는데도 사용했고, TTL이 긴 정보는 아직 사용할 수 있는데도 너무 빨리 버려서 불필요하게 upstream에 다시 물어보는 문제가 있었다.
이 실험에서 올바른 cache가 할 수 있는 최소 upstream query 수는 275번이었다. 처음 보는 이름이나 TTL이 끝난 이름은 새로운 정보를 받아야 하기 때문에, 만료된 정보를 사용하지 않는다면 275번보다 더 줄일 수 없다.
특히 www.microsoft.com은 TTL이 20초로 가장 짧고 자주 조회되기 때문에 baseline의 60초 저장 방식에서 가장 문제가 크게 나타나는 레코드였다.