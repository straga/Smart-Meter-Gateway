
import struct
import binascii

from scrivo.tools.tool import launch, asyncio, DataClassArg
from machine import UART

from .config import data_request, data_register_master, data_register_slave, panel_slave_addr
from .crc import check_crc16, calc_crc16

from scrivo import logging
log = logging.getLogger("MODBUS")
log.setLevel(logging.DEBUG)

reg_code = {
    0x01: 0,
    0x02: 10001,
    0x03: 40001,
    0x04: 30001,
}

def hexh(data,  sep=' '):
    try:
        data = f'{sep}'.join('{:02x}'.format(x) for x in data)
    except Exception as e:
        log.debug("error: HEX: {}".format(e))
    return data


class Runner:

    def __init__(self):
        launch(self._activate)

    async def _activate(self):

        self.request_data = []
        for key, value in data_request.items():
            self.request_data.append(DataClassArg(name=key, **value))

        self.meter_uart = UART(1, baudrate=9600, tx=13, rx=14)
        self.meter_swriter = asyncio.StreamWriter(self.meter_uart, {})
        self.meter_sreader = asyncio.StreamReader(self.meter_uart)

        self.panel_uart = UART(2, baudrate=9600, tx=21, rx=22)
        self.panel_swriter = asyncio.StreamWriter(self.panel_uart, {})
        self.panel_sreader = asyncio.StreamReader(self.panel_uart)
        self.panel_slave_addr = panel_slave_addr

        launch(self.meter_process)
        launch(self.panel_receiver)


    def make_request(self, request):
        quantity = request.qty_reg
        request_pdu = struct.pack('>BBHH', request.addr, request.func, request.start_reg, quantity)
        # debug
        log.debug(f"  Pdu Reguest : {hexh(request_pdu)}")

        modbus_pdu = bytearray()
        modbus_pdu.extend(request_pdu)
        modbus_pdu.extend(calc_crc16(request_pdu))
        # debug
        log.debug(f"  Pdu UART : {hexh(modbus_pdu)}")
        log.debug(" ")

        return modbus_pdu

    def parse_response(self, request, data):
        log.debug(f"<<recv: {hexh(data)}")
        if data[0] != request.addr or data[1] != request.func:
            return None

        crc, req_data = check_crc16(data)
        if crc:
            unit_addr, reg_func, byte_qty = struct.unpack_from('BBB', req_data, 0)
            request_offset = reg_code[reg_func] + request.start_reg
            # DEBUG
            log.debug(
                f"unit_addr: {unit_addr}, reg_offset: {request_offset}, byte_qty: {byte_qty}, data: {hexh(req_data)}")

            if request_offset in data_register_master:
                data_master = data_register_master[request_offset]
            else:
                data_register_master[request_offset] = {}
                data_master = data_register_master[request_offset]
                data_master['act'] = None

            data = req_data[3:]
            log.debug(f"<<recv value data: {hexh(data)}")
            data_master["alive"] = 10
            data_master["raw"] = data

            if data_master["act"] is not None:
                data_master["value"] = self._act(data_master["raw"], **data_master["act"])

            log.debug(" ")
            return True

    async def meter_process(self):

        while True:
            for request in self.request_data:
                request.alive -= 1
                uart_pdu = self.make_request(request)
                if uart_pdu is not None:
                    # send request to unit
                    await self.meter_swriter.awrite(uart_pdu)

                    await asyncio.sleep(0.2)
                    data = b''

                    # wait for response and read it
                    try:
                        data = await asyncio.wait_for(self.meter_sreader.read_uart(-1), 1)
                    except asyncio.TimeoutError:
                        log.error('Meter got timeout')
                    # log.info(f" << uart {'Meter'}: {hexh(data)}")

                    if data != b'':
                        # parse response data
                        if self.parse_response(request, data):
                            request.alive = 10
                            request.raw = data # response full.
            await asyncio.sleep(0.1)


    async def panel_receiver(self):

        while True:
            try:
                data = b''
                try:  # wait for response and read it
                    data = await asyncio.wait_for(self.panel_sreader.read_uart(-1), 1)
                except asyncio.TimeoutError:
                    log.debug('Panel got timeout')
                    await asyncio.sleep(5)
                    # emu for dev
                    # data = self.panel_emu()

                if data != b'':
                    pdu_response = self.panel_request_decode(data)
                    if pdu_response is not None:
                        await self.panel_swriter.awrite(pdu_response)
            except Exception as e:
                log.error("PANEL: {}".format(e))

    def panel_request_decode(self, request):
        value_byte = None
        # DEBUG
        log.debug(" ")
        log.debug(f" << uart request: {hexh(request)} - {len(request)}")

        if len(request) < 8:
            return None

        if request[0] not in self.panel_slave_addr:
            return None

        crc, request_data = check_crc16(request)
        # DEBUG
        log.debug(f"       crc check: {hexh(crc)}")

        if crc:
            # Request param
            unit_addr, reg_func, reg_addr, qty = struct.unpack_from('>BBHH', request_data, 0)  # 00: 00 : 00 00 : 00 00
            # DEBUG
            log.debug(f"   addr: {unit_addr}, func: {reg_func}, reg_addr: {reg_addr}, qty: {qty} ")

            # Calc offset
            reguest_offset = reg_code[reg_func]+reg_addr
            # DEBUG
            log.debug(f"   offset: {reguest_offset}")

            # Check if reguest exist, that map for request.
            if reguest_offset in data_register_slave:
                data_slave = data_register_slave[reguest_offset]
                master_offset = data_slave["master"]

                # if data exist in data_register_master
                if master_offset in data_register_master:
                    data_master = data_register_master[master_offset]

                    # DEBUG
                    log.debug(f"   - alive: {data_master['alive']}")

                    # get value if data alive
                    if data_master["alive"] >= 5:
                        data_master["alive"] -= 1
                        # get value from master record and conver for rigt response
                        if data_slave["act"] is not None:
                            value_byte = self._act(data_master["value"], **data_slave["act"])
                        # get value from master record, that is raw data from device
                        else:
                            value_byte = data_master["raw"]
                            # DEBUG
                            log.debug(f"   Modbus raw: {hexh(value_byte)}")
                            return value_byte

                # if -1, get value from action == emulate response
                elif master_offset == -1:
                    value_byte = self._act(**data_slave["act"])

            return self.make_pdu_response(unit_addr, reg_func, value_byte)

    def _act(self, value=None, **act):
        # DEBUG
        log.debug(f"   act : {act}")

        if value is None:
            value = act["value"]
        # DEBUG
        log.debug(f"   value: {value}")

        # pack value to bytes
        if "pack" in act:
            # convert value
            if "data_type" in act:
                data_type = act["data_type"]
                if data_type == "int":
                    value = int(value)
                if data_type == "float":
                    value = float(value)
                value * act["scale"]
                # DEBUG
                log.debug(f"   value convert: {value}")

            value_byte = struct.pack(act["pack"], value)
            # pack to len_byte+value_byte
            value = struct.pack("B", len(value_byte)) + value_byte
            # DEBUG
            log.debug(f"   act bytes: {hexh(value)}")

        if "unpack" in act:

            value = struct.unpack(act["unpack"], value)[0]
            # DEBUG
            log.debug(f"   act value: {value}")

        return value

    def make_pdu_response(self, unit_addr, reg_func, value_byte):
        if value_byte is not None:
            # DEBUG
            log.debug(f"  Modbus data:      {hexh(value_byte)}")

            modbus_pdu = bytearray()
            modbus_pdu.append(unit_addr)                    # unit_addr
            modbus_pdu.extend(struct.pack('B', reg_func))   # reg_func
            modbus_pdu.extend(value_byte)                   # value_byte
            modbus_pdu.extend(calc_crc16(modbus_pdu))       # crc

            # DEBUG
            log.debug(f"  Modbus Pdu: {hexh(modbus_pdu)}")

            return modbus_pdu
