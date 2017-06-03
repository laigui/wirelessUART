#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

from znldProtocol import Protocol

import binascii
from time import sleep
import json
import logging
import logging.config
logger = logging.getLogger(__name__)

def logger_init():
    ''' logging configuration in code, which is not in use any more.
    instead we are using dictConfig.
    '''
    from time import localtime, strftime
    log_filename = strftime("test-%y%m%d-%H:%M:%S.log", localtime())
    with open('logging_config.json', 'r') as logging_config_file:
        logging_config = json.load(logging_config_file)
        logging_config['handlers']['file']['filename'] = log_filename
        logging.config.dictConfig(logging_config)


if __name__ == "__main__":
    logger_init()
    file_name = 'node_config.json'
    with open(file_name, 'r') as node_config_file:
        node_config = json.load(node_config_file)
        logger.info('%s', node_config)

    try:
        role = node_config['role'].strip().upper()
        id = binascii.a2b_hex(node_config['id'].strip())
    except KeyError:
        logger.error('key errors (role, id) in configuration')
        exit(-1)

    if role == 'RC':
        hop = node_config['hop']
        e32_baudrate = node_config['e32']['baudrate']
        stations = node_config['stations']
        try:
            gui = node_config['gui'].strip().upper()
        except KeyError:
            gui = 'YES'

        if gui == 'NO':
            logger.debug('running in non-GUI mode')
            rc = Protocol(id=id, role=role, hop=hop, baudrate=e32_baudrate)
            rc.setName('Thread RC receiving')
            rc.setDaemon(True)
            try:
                rc.start()
                sleep(1)
                loop = 0
                led_ctrl = 0x3
                while loop < 10:
                    results = ''
                    mesg = chr(led_ctrl) + '\xFF\xFF'
                    logger.info('broadcast led_ctrl = %s' % repr(led_ctrl))
                    rc.RC_lamp_ctrl(Protocol.LampControl.BROADCAST_ID, mesg)
                    logger.info('poll led status from each STA:')
                    for (id, name) in stations.items():
                        if rc.RC_unicast_poll(binascii.a2b_hex(id), chr(led_ctrl)):
                            logger.info('%s (%s) response successfully' % (name, id))
                            results += name + '(1), '
                        else:
                            results += name + '(0), '
                    logger.info('***** loop = %s: %s*****' % (repr(loop), results))
                    loop += 1
                    if led_ctrl == 0x0:
                        led_ctrl = 0x3
                    else:
                        led_ctrl = 0x0
            except KeyboardInterrupt:
                logger.debug('Stopping Thread by Ctrl-C')
                rc.stop()
            except:
                import traceback
                traceback.print_exc()
            finally:
                logger.debug('Waiting for thread end')
                rc.join()
                logger.debug('End')
        else:
            logger.debug('running in GUI mode')

    elif role == 'STA':
        sta = Protocol(id=id, role=role)
        sta.setName('Thread STA receiving')
        sta.setDaemon(True)
        try:
            sta.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logger.debug('Stopping Thread by Ctrl-C')
            sta.stop()
        except:
            import traceback
            traceback.print_exc()
        finally:
            logger.debug('Waiting for thread end')
            sta.join()
            logger.debug('End')

    elif role == 'RELAY':
        relay = Protocol(id=id, role=role)
        relay.setName('Thread STA receiving')
        relay.setDaemon(True)
        try:
            relay.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            logger.debug('Stopping Thread by Ctrl-C')
            relay.stop()
        except:
            import traceback
            traceback.print_exc()
        finally:
            logger.debug('Waiting for thread end')
            relay.join()
            logger.debug('End')

    else:
        logger.error('role mistake in configuration!')