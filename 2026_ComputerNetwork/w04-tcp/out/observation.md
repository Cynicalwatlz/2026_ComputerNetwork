# Week 04 Observations

## Task 1
Stop-and-wait을 선택했고, ACK가 없으면 재전송하며 sequence number로 중복과 순서 변경을 처리했다.
2,000 bytes 전송 시 seed 246은 323 packets, seed 999는 299 packets가 필요했고 두 경우 모두 IDENTICAL이었다.

## Task 2
Handshake는 packet 1(SYN), 2(SYN-ACK), 3(ACK)이었고 Client/Server ISN은 373854892 / 2753130132였다. MSS=1400, SACK 허용, Window Scale도 확인했으며 scaled receive window는 131,072 bytes였지만 실제 in-flight는 더 작았다.
Wi-Fi는 136.24 Mbps, 15.4 ms였고 Hotspot은 16.91 Mbps, 38.9 ms였다. 더 긴 RTT는 ACK 반환을 늦춰 congestion window의 증가와 throughput에 영향을 줄 수 있다.

## Task 3
Baseline은 goodput이 높지만 loss 37.4%, retx 2340, avg queue 8.8로 비효율적이었다. 내 방식은 window를 약 20 packets 근처로 유지하여 goodput 98%, loss 0.5%, avg queue 4.9로 strong을 달성했다.
Backoff를 부드럽게 하면 goodput은 증가하지만 queue도 증가했으며, 최종 설정은 두 값의 균형을 맞췄다.