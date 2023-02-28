

SOLO     
```
self.meter_uart = UART(1, baudrate=9600, tx=13, rx=14)  <--> self.panel_uart = UART(2, baudrate=9600, tx=21, rx=22)   
┌─────────┐            ┌─────────┐            ┌─────────┐              ┌─────────┐            ┌──────────┐
│  Meter  │<--- A+ --->│         │<--- TX --->│         │<----- TX --->|         |            |          |
│         │<--- B- --->│  RS485  │<--- RX --->│  ESP32  │<----- RX --->|  RS485  |<--- A+ --->| Inverter |
│         │<--- GND -->│         │<--- GND -->|         |<----- GND -->|         |<--- B- --->|          |
│         │            │         │<--- 3.3V-->|         |<----- 3.3V-->|         |<--- GND -->|          |
└─────────┘            └─────────┘            └─────────┘              └─────────┘            └──────────┘
```
ESPNOW     
```
Client: self.meter_uart = UART(1, baudrate=9600, tx=13, rx=14)
┌─────────┐            ┌─────────┐            ┌─────────┐
│  Meter  │<--- A+ --->│         │<--- TX --->│         │
│         │<--- B- --->│  RS485  │<--- RX --->│  ESP32  │<---> Wifi/ESPNOW
│         │<--- GND -->│         │<--- GND -->|         |
│         │            │         │<--- 3.3V-->|         |
└─────────┘            └─────────┘            └─────────┘             

Server: self.panel_uart = UART(1, baudrate=9600, tx=13, rx=14)
┌─────────┐            ┌─────────┐            ┌─────────┐
│Inverter │<--- A+ --->│         │<--- TX --->│         │
│         │<--- B- --->│  RS485  │<--- RX --->│  ESP32  │<---> Wifi/ESPNOW
│         │<--- GND -->│         │<--- GND -->|         |
│         │            │         │<--- 3.3V-->|         |
└─────────┘            └─────────┘            └─────────┘   

```

### Inverter:
#### Tested
 - Solax - X1 mini any model , Gen2/Gen3
 - Deye - DSUN-3.6/5/6K-SG03LP1-EU

### Meter with RS485 Modbus:
 - EASTRON SDM230 1P or 3P
 - CHINT: 1P or 3P
 - Can be any Meter with Import/Export Watt.
 
### Board.
 - STM32 F411CE 8Mflash: https://www.aliexpress.com/item/1005001456186625.html
 - ESP32 any board.
 
### RS485 modbus
   UART <-> RS485: https://www.aliexpress.com/item/32705625990.html

### Info
#### version
- solo: esp32 or stm32 - need to change UART and config.py.
- espnow:  use two board esp32. One as Server, second as Client.
  for wireless data exchange Inverter and Meter.
  - https://micropython-glenn20.readthedocs.io/en/latest/library/espnow.html

#### More Details:
 - https://github.com/syssi/esphome-modbus-solax-x1/issues/20
