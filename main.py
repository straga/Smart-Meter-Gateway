from umodbus.serial import Serial as ModbusRTUMaster
from umodbus.modbus import ModbusRTU
import time
import struct

def main():

    # act as client, provide Modbus data via RTU to a host device
    #uart=1 (A9, A10) # (TX, RX)
    modbus_addr_slave = 1             # address on bus as client
    client = ModbusRTU(
        addr=modbus_addr_slave,
        uart_id=1,                     # UART ID for STM32
        baudrate=9600,                 # optional, default 9600
        data_bits=8,                   # optional, default 7
        stop_bits=1,                   # optional, default 1
        parity=None,
        name="solax")

    register_definitions = {
        "HREGS": {

            "1_HREG": {
                "register": 14,
                "len": 1,
            },
            "2_HREG": {
                "register": 11,
                "len": 1,
            },
            "3_HREG": {
                "register": 8,
                "len": 4,
            }
        },
    }

    client.setup_registers(registers=register_definitions, use_default_vals=True)
    reg_HREGS = client._register_dict['HREGS']
    print(reg_HREGS)

    # uart=2 (A2, A3) # (TX, RX)
    meter_addr = 1  # bus address of client
    meter = ModbusRTUMaster(
        uart_id=2,          # UART ID for STM32
        baudrate=9600,      # optional, default 9600
        data_bits=8,        # optional, default 7
        stop_bits=1,        # optional, default 1
        parity=None,        # optional, default None
        pins=None,
        name="meter")


    # READ HREGS read_holding_registers from Meter
    watt_register = 12 # 00 0C, 12+1 = read 13 and 14 registor
    watt_value = meter.read_input_registers(
        slave_addr=meter_addr,
        starting_addr=watt_register,
        register_qty=2,
        signed=True)

    print('Status of hreg {}: {}'.format(meter_addr, watt_value))
    print(client._register_dict)

    while True:
        # Read Modbus Request
        client.process()

        # Request watt from meter
        watt_value = meter.read_input_registers(
            slave_addr=meter_addr,
            starting_addr=watt_register,
            register_qty=2,
            signed=True)

        # Convert Float to Int
        watt = int(watt_value)
        # write Data int the Modbus register, that get read by Solax Invertor
        reg_HREGS[14] = [watt]

        print('Status of hreg {}: {}'.format(meter_addr, reg_HREGS[14]))

        time.sleep(0.1)


if __name__ == '__main__':
    print("MAIN")
    main()



