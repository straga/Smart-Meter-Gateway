
import uasyncio as asyncio
import uos

import _thread
import machine
from scrivo import logging

log = logging.getLogger('MAIN')
logging.basicConfig(level=logging.INFO)


storage_dir = "."
# WDT
async def run_wdt():
    import gc
    wdt = machine.WDT(timeout=12000)
    print("WDT RUN")
    while True:
        wdt.feed()
        gc.collect()
        # print("WDT RESET")
        await asyncio.sleep(5)

# Core
def core():
    # VFS SIZE
    fs_stat = uos.statvfs(storage_dir)
    fs_size = fs_stat[0] * fs_stat[2]
    fs_free = fs_stat[0] * fs_stat[3]
    log.info("File System Size {:,} - Free Space {:,}".format(fs_size, fs_free))

    part_name = uos.getcwd()
    log.info("PartName: {}".format(part_name))


# Lloader
async def loader():
    try:
        from scrivo_meter_client._runner import Runner
        log.info("Module: Run")
        meter = Runner()
    except Exception as e:
        log.error(f"Module: {e}")

def main():

    # Activate Core
    core()

    # AsyncIO in thread
    loop = asyncio.get_event_loop()
    _ = _thread.stack_size(8 * 1024)
    _thread.start_new_thread(loop.run_forever, ())

    # Run Loader Task
    loop.create_task(run_wdt())
    loop.create_task(loader())


if __name__ == '__main__':
    print("MAIN")
    main()


