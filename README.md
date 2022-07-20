## Gateway: 

First, that was to replace Solax Smart Meter(original meter impossible to buy) and Solax X1 mini Inverter.

### Inverter:

 - Solax - X1 mini any model , Gen2
 - Deye - DSUN-3.6/5/6K-SG03LP1-EU
 - Can be any Mete

### Meter  RS485  Modbus:

 - EASTRON SDM230 1P or 4P
 - CHINT: 1P or 3P
 - Can be any Meter with Import Export Watt.

### More Details:

 - https://github.com/syssi/esphome-modbus-solax-x1/issues/20

### Board.

 - STM32 F411CE 8Mflash: https://www.aliexpress.com/item/1005001456186625.html

   or

   ESP32 any board.

 - UART - RS485: https://www.aliexpress.com/item/32705625990.html

### Version

- solo: esp32 or stm32 - need to change UART and config.py.
- espnow:  use two board esp32. One as Server, second as Client.
for wireless data exchange Inverter and Meter.