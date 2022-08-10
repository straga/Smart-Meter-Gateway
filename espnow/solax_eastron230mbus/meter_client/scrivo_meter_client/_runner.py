import time
import struct
import binascii
import aioespnow

from scrivo.tools.tool import launch, asyncio, DataClassArg
from machine import UART

from .crc import check_crc16, calc_crc16

from scrivo import logging
log = logging.getLogger("MODBUS")
log.setLevel(logging.DEBUG)

def hexh(data,  sep=' '):
    try:
        data = f'{sep}'.join('{:02x}'.format(x) for x in data)
    except Exception as e:
        log.debug("error: HEX: {}".format(e))
    return data


data_register_master = {

    "deye_chint_1p": {
        "addr": 1,
        "func": 3,
        "start_reg": 8192,
        "qty_reg": 6,
        "alive": 10000, # 10000 for test - for real devices set: 0
        "raw": bytearray(b'\x02\x03\x05\x07'),
        "peer": b'\x29\x6F\x27\x04\x80\x64'  # server MAC address
    }
}


class Runner:

    def __init__(self):
        
        import network
        w0 = network.WLAN(network.STA_IF); w0.active(True)
        w0.config(ps_mode=network.WIFI_PS_NONE)  # ..then disable power saving
        w0 = network.WLAN(network.STA_IF); w0.active(True); w0.disconnect()
        w0.config(channel=6)    # Change to the channel.

        launch(self._activate)

    async def _activate(self):

        self.e_lan = aioespnow.AIOESPNow()
        self.e_lan.active(True)

        self.request_data = []
        for key, value in data_register_master.items():
            self.request_data.append(DataClassArg(name=key, **value))

        self.meter_uart = UART(1, baudrate=9600, tx=13, rx=14)
        self.meter_swriter = asyncio.StreamWriter(self.meter_uart, {})
        self.meter_sreader = asyncio.StreamReader(self.meter_uart)

        launch(self.meter_process)
        launch(self.espnow_process)


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
            unit_addr = data[0]
            func = data[1]
            len_data = struct.unpack_from('B', data[2:3])[0]
            raw_data = data[3:-2]

            log.debug(f"  addr: {unit_addr}, reg_addr: {func}={hex(func)}, len_data: {len_data}")
            log.debug(f"  data: {hexh(raw_data)}")
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
                        val_data = self.parse_response(request, data)
                        if val_data is not None:
                            request.value = val_data
                            request.alive = 10
                            request.raw = uart_pdu[0:4]+data # reguest addr, func, start_reg, qty_reg + response full.
            await asyncio.sleep(0.1)



    async def send_msg(self, peer, msg):
        import time
        before = time.ticks_us()
        if not await self.e_lan.asend(peer, msg):
            print("send: False")
            await asyncio.sleep(5)
        else:
            diff = time.ticks_diff(time.ticks_us(), before)
            print(f"send: True {diff}")
            await asyncio.sleep(0.5)

    async def espnow_process(self):

        while True:
            for request in self.request_data:
                if request.alive >= 5:
                    try:
                        await self.send_msg(request.peer, request.raw)
                    except OSError as err:
                        if len(err.args) > 1 and err.args[1] == 'ESP_ERR_ESPNOW_NOT_FOUND':
                            self.e_lan.add_peer(request.peer)
                            log.info(f"peers: {self.e_lan.get_peers}")

            await asyncio.sleep(0.1)


