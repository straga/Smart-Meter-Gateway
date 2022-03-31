
from scrivo.tools.tool import launch, asyncio, DataClassArg
from machine import UART

import struct

from scrivo import logging
log = logging.getLogger("MODBUS")
# log.setLevel(logging.DEBUG)

CRC16_TABLE = (
    0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241, 0xC601,
    0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440, 0xCC01, 0x0CC0,
    0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40, 0x0A00, 0xCAC1, 0xCB81,
    0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841, 0xD801, 0x18C0, 0x1980, 0xD941,
    0x1B00, 0xDBC1, 0xDA81, 0x1A40, 0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01,
    0x1DC0, 0x1C80, 0xDC41, 0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0,
    0x1680, 0xD641, 0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081,
    0x1040, 0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
    0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441, 0x3C00,
    0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41, 0xFA01, 0x3AC0,
    0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840, 0x2800, 0xE8C1, 0xE981,
    0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41, 0xEE01, 0x2EC0, 0x2F80, 0xEF41,
    0x2D00, 0xEDC1, 0xEC81, 0x2C40, 0xE401, 0x24C0, 0x2580, 0xE541, 0x2700,
    0xE7C1, 0xE681, 0x2640, 0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0,
    0x2080, 0xE041, 0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281,
    0x6240, 0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
    0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41, 0xAA01,
    0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840, 0x7800, 0xB8C1,
    0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41, 0xBE01, 0x7EC0, 0x7F80,
    0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40, 0xB401, 0x74C0, 0x7580, 0xB541,
    0x7700, 0xB7C1, 0xB681, 0x7640, 0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101,
    0x71C0, 0x7080, 0xB041, 0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0,
    0x5280, 0x9241, 0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481,
    0x5440, 0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
    0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841, 0x8801,
    0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40, 0x4E00, 0x8EC1,
    0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41, 0x4400, 0x84C1, 0x8581,
    0x4540, 0x8701, 0x47C0, 0x4680, 0x8641, 0x8201, 0x42C0, 0x4380, 0x8341,
    0x4100, 0x81C1, 0x8081, 0x4040
)

CRC_LENGTH = 0x02

# Register Table
# 1-9999	    0000 to 270E	        R/W	    Discrete Output Coils	            DO
# 10001-19999	0000 to 270E    	    R	    Discrete Input Contacts	            DI
# 30001-39999	0000 to 270E	        R	    Analog Input Registers	            AI
# 40001-49999	0000 to 270E	        R/W	    Analog Output Holding Registers	    AO

# Data type
# 16-bit unsigned integer	                           0 to 65535	                    AE 41	     44 609
# 16-bit signed integer             	               -32768 to 32767	                AE 41	     -20 927
# two character ASCII string	                       2 char	                        AE 41	     ® A
# discrete on/off value	                               0 and 1	                        00 01	     0001
# 32-bit unsigned integer	                           0 to 4,294,967,295	            AE 41 56 52	 2 923 517 522
# 32-bit signed integer	                              -2,147,483,648 to 2,147,483,647	AE 41 56 52	 -1 371 449 774
# 32-bit single precision IEEE floating point number   1,2·10−38 to 3,4×10+38	        AE 41 56 52	 -4.395978 E-11
# four character ASCII string	                       4 char	                        AE 41 56 52	 ® A V R

# Func commnad
# 01 (0x01)	Read DO	                Read Coil Status	        Discrete	Read
# 02 (0x02)	Read DI	                Read Input Status	        Discrete	Read
# 03 (0x03)	Read AO	                Read Holding Registers	    16 bit	    Read
# 04 (0x04)	Read AI	                Read Input Registers	    16 bit	    Read
# 05 (0x05)	Write one DO	        Force Single Coil	        Discrete	Write
# 06 (0x06)	Write one AO	        Preset Single Register	    16 bit	    Write
# 15 (0x0F)	Multiple DO recording	Force Multiple Coils	    Discrete	Write
# 16 (0x10)	Multiple AO recording	Preset Multiple Registers	16 bit	    Write

# func: 03, Read AO, 40001-49999


def calculate_crc16(req_data, req_crc=None):
    crc = 0xFFFF
    # log.debug(f"reg_crc: {hexh(reg_crc)} req_data: {hexh(req_data)}")
    for char in req_data:
        crc = (crc >> 8) ^ CRC16_TABLE[(crc ^ char) & 0xFF]

    crc = struct.pack('<H', crc)

    if req_crc is not None:
        if (req_crc[0] != crc[0]) or (req_crc[1] != crc[1]):
            # log.debug(f"CRC calc: {crc} != reg: {reg_crc}")
            return None
    return crc


def hexh(data):
    try:
        data = ' '.join('{:02x}'.format(x) for x in data)
    except Exception as e:
        log.error("HEX: {}".format(e))

    return data


class Runner:
    def __init__(self):
        launch(self._activate)

    async def _activate(self):
        self.unit_addr_list = [0x01]

        # h short           integer     2
        # H unsigned short  integer     2

        # self.data_register = {
        #     40012: {"dtype": "H", "value": 0, "state}, 01 03 00 0b 00 01 CR1 CR2 - 00 0b = 11+1 = 12 - detect
        #     40015: {"dtype": "h", "value": 150}, 01 03 00 0e 00 01 CR1 CR2 - 00 0e = 14+1 = 15 - watt
        # }
        #
        # self.data_register_slave = {
        #     30013: {"dtype": "f", "value": 0}, get data from slave meter 12 = 12+1 = 13, 13 = 13+1 = 14
        #     30014: {"dtype": "x", "value": 0}
        # }

        # struct.unpack(">h", b'\x00\x0C')
        # (12,) +1, len= 2 regisr fun code = 4(30001-39999) = 30013-3014

        self.data_register_master = {
            "watts": {
                "addr": 1,
                "func": 4,
                "start_reg": 12,
                "len": 2,
                "action": ">f",
                "scale": 1,
                "value": 0,
                "unit": "W",
                "alive": 0,
            },

            "detect":{
                "addr": 0,
                "func": 0,
                "start_reg": 0,
                "len": 0,
                "action": "x",
                "scale": 1,
                "value": 0,
                "unit": "",
                "alive": 0,
            },
        }

        self.data_register_slave = {

            #ask from: func 03 , 00 0e = 14+1
            40015: {
                "master": "watts",
                "func": 3,
                "len": 1,
                "value": 0,
                "act": "h",
                "type": "int",
                "scale": 1,
            },

            # ask from: func 03,  00 0b = 11+1
            40012: {
                "master": "detect",
                "func": 0,
                "len": 1,
                "value": 0,
                "act": "H",
                "type": "int",
                "scale": 1,
            }
        }

    #     UART_1
    #     define MICROPY_HW_UART1_TX     (pin_A9)
    #     define MICROPY_HW_UART1_RX     (pin_A10)

    #     UART_2
    #     define MICROPY_HW_UART2_TX     (pin_A9)
    #     define MICROPY_HW_UART2_RX     (pin_A10)

        self.panel_uart = UART(1, baudrate=9600)
        self.panel_swriter = asyncio.StreamWriter(self.panel_uart, {})
        self.panel_sreader = asyncio.StreamReader(self.panel_uart)
        self.panel_slave_addr = [1]

        self.meter_uart = UART(2, baudrate=9600)
        self.meter_swriter = asyncio.StreamWriter(self.meter_uart, {})
        self.meter_sreader = asyncio.StreamReader(self.meter_uart)



        self.loop = asyncio.get_event_loop()

        launch(self.meter_request)
        launch(self.panel_receiver)

    async def meter_request(self):
        while True:
            try:
                for key, value in self.data_register_master.items():
                    value["alive"] = 0

                    if value["len"] > 0: # if len = 0, no need to request, just emulated value.
                        request = DataClassArg(name=key, **value)  # create obje frim dict
                        uart_pdu = self.make_request(request)      # make request data

                        if uart_pdu is not None:
                            log.info(f" >> uart {'Meter'}: {hexh(uart_pdu)}")
                            await self.meter_swriter.awrite(uart_pdu)  # send request to unit
                            data = b''
                            try: # wait for response and read it
                                data = await asyncio.wait_for(self.meter_sreader.read(-1), 1)
                            except asyncio.TimeoutError:  # Mandatory error trapping
                                log.error('Meter got timeout')  # Caller sees TimeoutError

                            log.info(f" << uart {'Meter'}: {hexh(data)}")

                            val_data = self.parse_response(request, data) # parse response data
                            if val_data is not None:
                                value["value"] = val_data  # update value register
                                value["alive"] = 1
                    else:
                        value["alive"] = 1

            except Exception as e:
                log.error(f" >> uart Meter: {e}")

            await asyncio.sleep(0.1)
            # log.debug(f"register: {self.data_register_master}")

    def make_request(self, request):
        quantity = request.len
        modbus_pdu = struct.pack('>BHH', request.func, request.start_reg, quantity)

        log.debug(f"MODBUS Pdu: {hexh(modbus_pdu)}")

        serial_pdu = bytearray()
        serial_pdu.append(request.addr)
        serial_pdu.extend(modbus_pdu)
        crc = calculate_crc16(serial_pdu)

        if crc:
            serial_pdu.extend(crc)
            log.debug(f"UART Pdu: {hexh(serial_pdu)}")
            return serial_pdu


    def parse_response(self, request, data):
        if data[0] != request.addr or data[1] != request.func:
            return None

        req_crc = data[-CRC_LENGTH:]
        req_data = data[:-CRC_LENGTH]
        # log.debug(f"CRC: {req_crc}, data: {req_data}")
        crc = calculate_crc16(req_data, req_crc)

        log.debug(f"crc check: {hexh(req_crc)} == {hexh(crc)}")

        if crc:
            unit_addr = data[0]
            func = data[1]
            len_data = data[2]
            log.debug(f"addr: {unit_addr}, reg_addr: {func}, len: {len_data}")
            raw_data = data[3:-2]
            val_data = struct.unpack(request.action, raw_data)[0]
            log.debug(f"data -> raw: {hexh(req_data)}, value: {val_data}")
            return val_data


    async def panel_receiver(self):

        while True:
            try:
                data = b''
                try:  # wait for response and read it
                    data = await asyncio.wait_for(self.panel_sreader.read(-1), 1)
                except asyncio.TimeoutError:  # Mandatory error trapping
                    log.error('Meter got timeout')  # Caller sees TimeoutError

                log.info(f" << uart {'Panel'}: {hexh(data)}")
                serial_pdu = self.get_request(data)
                if serial_pdu is not None:
                    await self.panel_swriter.awrite(serial_pdu)
                    log.info(f" >> uart {'Panel'}: {hexh(serial_pdu)}")
            except Exception as e:
                log.error("PANEL: {}".format(e))

    def value_conver(self, data, data_type):
        if data_type == "int":
            return int(data)
        if data_type == "float":
            return float(data)

    def get_request(self, req):

        if len(req) < 8:
            return None

        if req[0] not in self.panel_slave_addr:
            return None

        req_crc = req[-CRC_LENGTH:]
        req_data = req[:-CRC_LENGTH]
        crc = calculate_crc16(req_data, req_crc)

        log.debug(f"crc check {'Panel'}: {hexh(crc)}")

        if crc:
            unit_addr = req[0]

            # Read AO
            function, register_addr = struct.unpack_from('>BH', req_data, 1)
            quantity = struct.unpack_from('>H', req_data, 4)[0]
            log.debug(f"addr: {unit_addr}, func: {function}, reg_addr: {register_addr}, qty: {quantity} ")


            if function == 3 and len(req) == 8:    # Read AO with 8 bytes
                register_read = 40001+register_addr
                log.debug(f"register for read {'Panel'}: {register_read}")

                if register_read in self.data_register_slave:
                    data_register_slave = self.data_register_slave[register_read]
                    data_register_master = self.data_register_master[data_register_slave["master"]]

                    if data_register_master["alive"] == 1:
                        data_register_slave["value"] = self.value_conver(data_register_master["value"], data_register_slave["type"])

                        fmt = data_register_slave["act"]
                        value_len = data_register_slave["len"]
                        value = data_register_slave["value"]

                        log.debug(f"Reg Data - {register_read}: {value}")

                        modbus_pdu = struct.pack('>BB' + fmt, function, value_len * 2, value)

                        log.debug(f"MODBUS Pdu: {hexh(modbus_pdu)}")

                        serial_pdu = bytearray()
                        serial_pdu.append(unit_addr)
                        serial_pdu.extend(modbus_pdu)
                        crc = calculate_crc16(serial_pdu)
                        serial_pdu.extend(crc)

                        log.debug(f"Serial Pdu: {hexh(serial_pdu)}")

                        return serial_pdu

