"""
Smart Meter Gateway - Production Version
STM32 Blackpill F411
UART1: Poll Eastron meter (master)
UART2: Respond to Solax/Deye panel (slave)
"""

import struct
from scrivo.tools.tool import launch, asyncio, DataClassArg
from machine import UART
from scrivo import logging

from .config import (
    data_request, data_register_master, data_register_slave, panel_slave_addr,
    METER_UART_ID, PANEL_UART_ID
)
from .crc import check_crc16, calc_crc16

log = logging.getLogger("GATEWAY")
log.setLevel(logging.INFO)


def hexh(data, sep=' '):
    """Convert bytes to hex string"""
    try:
        return f'{sep}'.join('{:02x}'.format(x) for x in data)
    except Exception:
        return str(data)


# Modbus register offset codes
reg_code = {
    0x01: 0,      # Coil
    0x02: 10001,  # Discrete Input
    0x03: 40001,  # Holding Register
    0x04: 30001,  # Input Register
}


class Runner:

    def __init__(self):
        launch(self._activate)

    async def _activate(self):
        log.info("Smart Meter Gateway - STM32")

        # Prepare request list
        self.request_data = []
        for key, value in data_request.items():
            self.request_data.append(DataClassArg(name=key, **value))

        # Initialize UARTs (STM32: pins are fixed by UART number)
        self.meter_uart = UART(METER_UART_ID, baudrate=9600, bits=8, parity=None, stop=1)
        self.panel_uart = UART(PANEL_UART_ID, baudrate=9600, bits=8, parity=None, stop=1)

        log.info("UART1 (Meter): PA9/PA10")
        log.info("UART2 (Panel): PA2/PA3")
        log.info("Gateway ready")

        # Launch gateway tasks
        launch(self.meter_process)
        launch(self.panel_receiver)

    def make_request(self, request):
        """Create Modbus request with CRC"""
        pdu = struct.pack('>BBHH', request.addr, request.func, request.start_reg, request.qty_reg)
        modbus_pdu = bytearray(pdu)
        modbus_pdu.extend(calc_crc16(pdu))
        return modbus_pdu

    def parse_response(self, request, data):
        """Parse meter response and store in data_register_master"""
        if data[0] != request.addr or data[1] != request.func:
            return None

        crc, req_data = check_crc16(data)
        if not crc:
            return None

        unit_addr, reg_func, byte_qty = struct.unpack_from('BBB', req_data, 0)
        request_offset = reg_code[reg_func] + request.start_reg

        # Get or create register entry
        if request_offset in data_register_master:
            data_master = data_register_master[request_offset]
        else:
            data_register_master[request_offset] = {}
            data_master = data_register_master[request_offset]
            data_master['act'] = None

        # Extract data
        data_value = req_data[3:]
        data_master["alive"] = 10
        data_master["raw"] = data_value

        # Convert if action specified
        if data_master["act"] is not None:
            data_master["value"] = self._act(data_master["raw"], **data_master["act"])
            # Only log power data
            if request_offset == 30013:
                log.info(f"Power: {data_master['value']} {data_master['act'].get('unit', '')}")

        return True

    async def meter_process(self):
        """Poll meter periodically"""
        while True:
            for request in self.request_data:
                request.alive -= 1
                uart_pdu = self.make_request(request)

                if uart_pdu is not None:
                    # Send request
                    self.meter_uart.write(uart_pdu)
                    await asyncio.sleep(0.2)

                    # Read response
                    if self.meter_uart.any():
                        data = self.meter_uart.read()

                        if data != b'':
                            # Parse and store
                            if self.parse_response(request, data):
                                request.alive = 10
                                request.raw = data

            await asyncio.sleep(0.5)

    async def panel_receiver(self):
        """Receive panel requests and respond"""
        while True:
            await asyncio.sleep(0.05)

            # Check for incoming request
            if self.panel_uart.any():
                request = self.panel_uart.read()

                if len(request) >= 8 and request[0] in panel_slave_addr:
                    pdu_response = self.panel_request_decode(request)
                    if pdu_response is not None:
                        self.panel_uart.write(pdu_response)

    def panel_request_decode(self, request):
        """Decode panel request and build response"""
        # Validate CRC
        crc, request_data = check_crc16(request)
        if not crc:
            return None

        # Parse request
        unit_addr, reg_func, reg_addr, qty = struct.unpack_from('>BBHH', request_data, 0)

        # Calculate offset
        request_offset = reg_code[reg_func] + reg_addr

        # Check if request mapped in config
        if request_offset not in data_register_slave:
            log.warning(f"Unmapped register {request_offset}")
            return None

        data_slave = data_register_slave[request_offset]
        master_offset = data_slave["master"]

        value_byte = None

        # Get value from master register
        if master_offset in data_register_master:
            data_master = data_register_master[master_offset]

            if data_master["alive"] >= 5:
                data_master["alive"] -= 1

                # Convert value if action specified
                if data_slave["act"] is not None:
                    value_byte = self._act(data_master["value"], **data_slave["act"])
                else:
                    # Send raw data
                    value_byte = data_master["raw"]

            else:
                log.warning("Meter data stale")
                return None

        # Emulate static value (master=-1)
        elif master_offset == -1:
            value_byte = self._act(**data_slave["act"])

        else:
            log.warning(f"Master register {master_offset} not found")
            return None

        # Build response
        return self.make_pdu_response(unit_addr, reg_func, value_byte)

    def _act(self, value=None, **act):
        """Convert data according to action spec"""
        if value is None:
            value = act["value"]

        # Unpack (bytes → value)
        if "unpack" in act:
            value = struct.unpack(act["unpack"], value)[0]

        # Pack (value → bytes)
        if "pack" in act:
            # Convert data type
            if "data_type" in act:
                data_type = act["data_type"]
                if data_type == "int":
                    value = int(value)
                elif data_type == "float":
                    value = float(value)
                value = value * act.get("scale", 1)

            value_byte = struct.pack(act["pack"], value)
            # Prepend byte count
            value = struct.pack("B", len(value_byte)) + value_byte

        return value

    def make_pdu_response(self, unit_addr, reg_func, value_byte):
        """Build Modbus response with CRC"""
        if value_byte is not None:
            modbus_pdu = bytearray()
            modbus_pdu.append(unit_addr)
            modbus_pdu.extend(struct.pack('B', reg_func))
            modbus_pdu.extend(value_byte)
            modbus_pdu.extend(calc_crc16(modbus_pdu))
            return modbus_pdu
        return None
