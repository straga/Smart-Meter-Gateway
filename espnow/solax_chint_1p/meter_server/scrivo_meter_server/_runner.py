
import binascii
import struct
import aioespnow
from machine import UART
from scrivo.tools.tool import launch, asyncio
from .crc import calc_crc16, check_crc16

from scrivo import logging
log = logging.getLogger("MODBUS")
log.setLevel(logging.DEBUG)


def hexh(data,  sep=' '):
    try:
        data = f'{sep}'.join('{:02x}'.format(x) for x in data)
    except Exception as e:
        log.error("HEX: {}".format(e))
    return data


#TODO: move to json config
data_register_master = {
    30013: {
        "alive": 0,
        "raw": b'\x00',
        "value": 0,
        "act": {"unpack": ">f", "scale": 1, "unit": "W", },
    },
    48193: {
        "alive": 0,
        "raw": binascii.unhexlify("01030c436a4ccd000000000000000083ec"),
        "value": 0,
        "act": None,
    },
}


#TODO: move to json config
data_register_slave = {

    # solax ask from: func 03 , 00 0e = 14+1 = offset 40015
    40015: {
        "master": 30013,
        "func": 0x03,
        "act": {"pack": ">h", "scale": 1, "data_type": "int"}
    },

    # solax ask from: func 03,  00 0b = 11+1 = offset 40012
    40012: {
        "master": -1,
        "func": 0x03,
        "act": {"pack": ">h", "scale": 1, "value": 0}
    },

    # solax ask from: func 03, 8+1 = offset 40009
    40009: {
        "master": -1,
        "func": 0x03,
        "act": {"pack": ">h", "scale": 1, "value": 0}
    },

    48193: {
        "master": 48193,
        "func": 0x03,
        "act": None
    },


}

reg_code = {
    0x01: 0,
    0x02: 10001,
    0x03: 40001,
    0x04: 30001,
}

peer = b'\x24\x68\x28\x04\x70\x0C'  # client MAC address Real Meter


panel_slave_addr = [1]

class Runner:

    def __init__(self):
        
        import network
        w0 = network.WLAN(network.STA_IF); w0.active(True)
        w0.config(ps_mode=network.WIFI_PS_NONE)  # ..then disable power saving
        w0 = network.WLAN(network.STA_IF); w0.active(True); w0.disconnect()
        w0.config(channel=6)    # Change to the channel.

        launch(self._activate)



    async def _activate(self):

        await asyncio.sleep(30)

        self.e_lan = aioespnow.AIOESPNow()  # Returns AIOESPNow enhanced with async support 24:6F:28:04:80:64 24:6F:28:04:71:1C
        self.e_lan.active(True)
        self.e_lan.add_peer(peer)

        self.panel_uart = UART(1, baudrate=9600, tx=13, rx=14)
        self.panel_swriter = asyncio.StreamWriter(self.panel_uart, {})
        self.panel_sreader = asyncio.StreamReader(self.panel_uart)
        self.panel_slave_addr = panel_slave_addr

        launch(self.espnow_meter_server)
        launch(self.panel_receiver)


    async def espnow_meter_server(self):
        async for mac, msg in self.e_lan:
            # DEBUG
            log.debug(" ")
            log.debug(f"recv: {hexh(msg)}")
            try:
                # msg = memoryview(msg)
                # messege from espnow meter
                # 01 04 00 0c - 01 04 04 c2 2c 92 3c 6a 84
                # log.debug(f"recv: {hexh(msg)}")
                # reg_func, reg_addr (01 04 00 0c) from request: 01 04 00 0c 00 02 b1 c8

                remote_unit_addr, remote_reg_func, remote_reg_addr = struct.unpack_from('>BBH', msg, 0)
                reg_offset = reg_code[remote_reg_func] + remote_reg_addr
                # DEBUG
                log.debug(f"Remote: unit_addr: {remote_unit_addr}, reg_func: {remote_reg_func}, reg_addr: {remote_reg_addr}")
                log.debug(f"Remote: offset: {reg_offset}")

                # Modbus response from meter
                # 01 04 04 c2 2c 92 3c 6a 84 - crc: 6a 84
                # fist 3 bytes are header request reg_func and reg_addr, data= raw modbus response from meter
                crc, modbus_pdu = check_crc16(msg[4:])
                # DEBUG
                log.debug(f"CRC: {hexh(crc)}")

                # 01 04 04 c2 2c 92 3c - data from crc check
                if crc:
                    unit_addr, reg_func, byte_qty = struct.unpack_from('BBB', modbus_pdu, 0)
                    # DEBUG
                    log.debug(
                        f"unit_addr: {unit_addr}, reg_offset: {reg_offset}, byte_qty: {byte_qty}, data: {hexh(modbus_pdu)}")

                    # cut unit_addr, reg_func, data_bytes_qty
                    val_data = modbus_pdu[3:]
                    # data 4 byte = c2 2c 92 3c

                    _record = data_register_master[reg_offset]
                    # DEBUG
                    log.debug(f"act: {_record}")

                    if _record["act"] is not None:
                        _record["value"] = self._act(val_data, **_record["act"])

                    _record["alive"] = 10
                    _record["raw"] = modbus_pdu

            except Exception as e:
                log.error("meter_server: {}".format(e))




    # log.debug("panel_emu")
    # # dayie: 01 03 20 00 00 06 ce 08
    # panel_emu_data_request = ["0103000e0001e5c9", "0103000b0001f5c8", "010300080004c5cb", "010320000006ce08"]
    # panel_emu_idx = 0
    #
    # def panel_emu(self):
    #     data = binascii.unhexlify(self.panel_emu_data_request[self.panel_emu_idx])
    #     self.panel_emu_idx += 1
    #     if self.panel_emu_idx == len(self.panel_emu_data_request):
    #         self.panel_emu_idx = 0
    #     return data

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
